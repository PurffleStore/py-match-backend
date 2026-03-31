# routes/llm_routes.py
from flask import Blueprint, request, jsonify
import uuid
from llm_service import (
    SessionState, SESSIONS, save_sessions, persist_final_progress,
    choose_themes, generate_batch_questions
)
# Import fetch_profile_for_role from database instead of llm_service
from database import fetch_profile_for_role

llm_bp = Blueprint('llm', __name__)


# ==============================================
# UPDATED: llm_start with better tracking
# ==============================================
@llm_bp.route('/llm/start', methods=['POST'])
def llm_start():
    data = request.get_json(force=True) or {}
    user_id = str(data.get("user_id") or "").strip()
    role_in = (data.get("role") or "general").lower()
    n_req = int(data.get("n_questions", 20))
    b_req = int(data.get("batch_size", 10))

    print(f"🚀 STARTING ASSESSMENT FOR USER: {user_id}, ROLE: {role_in}")
    
    if not user_id:
        print("❌ ERROR: user_id is required")
        return jsonify({"error": "user_id is required"}), 400
    
    # Fetch profile and expectation
    profile = fetch_profile_for_role(user_id, role_in)
    
    expectation = {}
    try:
        from database import fetch_expectation_data
        # Pass only user_id if function takes 1 argument
        expectation = fetch_expectation_data(user_id)
    except Exception as e:
        print(f"⚠️ Could not fetch expectation data: {e}")
        from llm_service import extract_all_user_data
        all_data = extract_all_user_data(user_id, role_in)
        expectation = all_data.get("expectation", {})

    print(f"📊 Got profile: {len(profile)} fields, expectation: {len(expectation)} fields")

    # Create session
    sid = str(uuid.uuid4())
    sess = SessionState(
        n_questions=n_req,
        batch_size=b_req,
        domain=role_in,
        role=role_in,
        profile=profile,
        expectation=expectation
    )
    SESSIONS[sid] = sess

    try:
        # Generate themes
        to_generate = min(sess.batch_size, sess.remaining())
        themes = choose_themes(sess, to_generate)
        
        print(f"🎯 Generating {to_generate} questions from {len(themes)} themes")

        # Generate questions - NO FALLBACK
        queue = generate_batch_questions(
            themes, 
            sess.to_min_state(), 
            context="", 
            previous_questions=sess.all_asked_questions
        )

        if not queue:
            print("❌ ERROR: Question generation returned empty")
            return jsonify({"error": "Question generation failed"}), 500

        sess.queue = queue

        # Serve first question
        first = sess.queue.pop(0)
        sess.asked += 1
        sess.all_asked_questions.append(first["question"])

        print(f"✅ First question ready: {first['question'][:50]}...")

        save_sessions()

        return jsonify({
            "session_id": sid,
            "index": 1,
            "total": sess.n_questions,
            "question": first["question"],
            "options": first["options"],
            "source": first.get("source", "unknown"),
            "role": sess.role,
            "book_based": first.get("book_based", False),
            "simple_english": first.get("simple_english", False),
            "question_type": first.get("question_type", "unknown"),
        })
    
    except Exception as e:
        print(f"❌❌❌ SESSION START FAILED: {e}")
        if sid in SESSIONS:
            del SESSIONS[sid]
        return jsonify({
            "error": "Assessment failed",
            "message": str(e),
            "llm_required": True
        }), 500



@llm_bp.route('/llm/next', methods=['POST'])
def llm_next():
    data = request.get_json(force=True) or {}
    sid = data.get("session_id")
    color = str(data.get("selected_color") or "").lower()

    if not sid or sid not in SESSIONS:
        return jsonify({"error": "Invalid or missing session_id"}), 400
    if color not in ["blue", "green", "red", "yellow"]:
        return jsonify({"error": "selected_color must be blue|green|red|yellow"}), 400

    sess = SESSIONS[sid]
    if sess.finished:
        return jsonify({"done": True, "message": "Session already finished."})

    # record answer
    sess.color_counts[color] += 1
    sess.history.append({"selected_color": color})

    # Initialize themes and context with default values
    themes = []
    context = ""

    # finished?
    if sess.asked >= sess.n_questions:
        sess.finished = True
        mix = sess.to_min_state()["mix"]
        user_id = (sess.profile or {}).get("user_id")
        db_ok = persist_final_progress(user_id=user_id, role=sess.role, mix=mix)
        save_sessions()
        return jsonify({
            "done": True,
            "message": "No more questions.",
            "mix": mix,
            "db_write": "ok" if db_ok else "failed"
        })

    # ensure queue; refill if needed
    if not sess.queue:
        to_generate = min(sess.batch_size, sess.remaining())
        themes = choose_themes(sess, to_generate)

        try:
            from faiss_service import HAS_FAISS, FAISS_INDEX, TEXT_CHUNKS
            if HAS_FAISS and FAISS_INDEX is not None and TEXT_CHUNKS:
                import random
                context = "\n".join(random.sample(TEXT_CHUNKS, min(3, len(TEXT_CHUNKS))))
        except ImportError:
            pass

        # Generate questions - FIXED: use sess.all_asked_questions instead of sess.history_of_questions
        sess.queue = generate_batch_questions(themes, sess.to_min_state(), context=context, previous_questions=sess.all_asked_questions)

        if not sess.queue:
            return jsonify({"error": "Question generation failed"}), 500

    nxt = sess.queue.pop(0)
    sess.asked += 1

    # Track the asked question - FIXED: use sess.all_asked_questions instead of sess.history_of_questions
    sess.all_asked_questions.append(nxt["question"])

    save_sessions()

    return jsonify({
        "session_id": sid,
        "index": sess.asked,
        "total": sess.n_questions,
        "question": nxt["question"],
        "options": nxt["options"],
        "progress": sess.to_min_state()["mix"],
        "source": nxt.get("source", "unknown"),
        "role": sess.role,
        # ✅ ADD THESE:
        "faiss_context": nxt.get("faiss_context", ""),
        "faiss_themes": nxt.get("faiss_themes", []),
    })