# routes/matching_routes.py
from flask import Blueprint, request, jsonify, current_app
import numpy as np
from sqlalchemy import func
import traceback

from models import LLMGeneratedQuestions, Marriage, Users, ExpectationResponse, db
from matching_functions import match_expectation_with_profiles, generate_expectation_explanation
from character_functions import cosine_sim, generate_character_llm_explanation, generate_character_fallback_explanation
from database import fetch_expectation_data, fetch_marriage_profile_data
from config import COLOR_KEYS

matching_bp = Blueprint('matching', __name__)


@matching_bp.route('/match', methods=['GET'])
@matching_bp.route('/match/<int:user_id>', methods=['GET'])
@matching_bp.route('/api/match', methods=['GET'])
@matching_bp.route('/api/match/<int:user_id>', methods=['GET'])
def unified_match(user_id=None):
    """Unified match endpoint that handles all three modes"""

    # Get user_id from either path parameter or query parameter
    if user_id is None:
        try:
            user_id = int(request.args.get("user_id", ""))
        except ValueError:
            return jsonify({"error": "Missing or invalid user_id"}), 400

    # Get parameters
    role = request.args.get("role", None)
    limit = int(request.args.get("limit", "10"))
    exclude_self = request.args.get("exclude_self", "yes").lower() == "yes"
    mode = request.args.get("mode", "expectation-only")  # Default to expectation-only

    print(f"🔍 DEBUG: Match request - user_id: {user_id}, mode: {mode}")

    # 1) EXPECTATION ONLY
    if mode == "expectation-only":
        print("🎯 Using PURE EXPECTATION matching")

        expectation_matches = match_expectation_with_profiles(user_id)

        if not expectation_matches:
            return jsonify({"error": f"No matches found for user_id={user_id}"}), 404

        matches_by_range = {
            "90-100": [],
            "80-89": [],
            "70-79": [],
            "60-69": [],
            "below_60": []
        }

        for match in expectation_matches:
            score_percentage = match.get("expectation_score", 0) * 100

            if score_percentage >= 90:
                range_key = "90-100"
            elif score_percentage >= 80:
                range_key = "80-89"
            elif score_percentage >= 70:
                range_key = "70-79"
            elif score_percentage >= 60:
                range_key = "60-69"
            else:
                range_key = "below_60"

            match_obj = {
                "user_id": match["user_id"],
                "name": match["name"],
                "gender": match.get("gender", ""),
                "city": match.get("location", ""),
                "score_expect": match.get("expectation_score", 0),
                "score_color": match.get("character_score", 0),
                "final_score": round(score_percentage, 2),
                "blue": 0,
                "green": 0,
                "yellow": 0,
                "red": 0,
                "explanations": [],
                "explanation_source": "expectation"
            }

            matches_by_range[range_key].append(match_obj)

        user = Users.query.filter_by(user_id=user_id).first()

        input_user = {
            "user_id": user_id,
            "role": "marriage",
            "name": user.name if user else "Unknown",
            "blue": 0,
            "green": 0,
            "yellow": 0,
            "red": 0,
            "created_at": None,
        }

        print(f"✅ DEBUG: Returning {len(expectation_matches)} pure expectation matches")

        return jsonify({
            "input_user": input_user,
            "matches": matches_by_range,
            "count": len(expectation_matches),
            "mode": "expectation-only"
        })

    # 2) CHARACTER ONLY
    elif mode == "character":
        print("🎯 Using PURE CHARACTER matching - NO EXPECTATION FILTERING")

        current_user = Marriage.query.filter_by(user_id=user_id).first()
        if not current_user:
            return jsonify({"error": f"No marriage profile found for user_id={user_id}"}), 404

        user_gender = (current_user.gender or "").lower()
        print(f"🔍 DEBUG: Current user gender: {user_gender}")

        if user_gender.startswith('male'):
            opposite_profiles = Marriage.query.filter(
                func.lower(func.trim(Marriage.gender)) == "female"
            ).all()
        elif user_gender.startswith('female'):
            opposite_profiles = Marriage.query.filter(
                func.lower(func.trim(Marriage.gender)) == "male"
            ).all()
        else:
            opposite_profiles = Marriage.query.filter(
                Marriage.gender != current_user.gender
            ).all()

        print(f"🔍 DEBUG: Found {len(opposite_profiles)} opposite gender profiles (NO MANDATORY FILTERING)")

        base_llm = LLMGeneratedQuestions.query.filter_by(user_id=user_id).first()
        if not base_llm:
            return jsonify({"error": f"No character data found for user_id={user_id}"}), 404

        u_vec = base_llm.color_vec()

        candidates = []
        all_ids = [profile.user_id for profile in opposite_profiles]

        llm_data = LLMGeneratedQuestions.query.filter(
            LLMGeneratedQuestions.user_id.in_(all_ids)
        ).all()
        llm_map = {l.user_id: l for l in llm_data}

        for profile in opposite_profiles:
            if profile.user_id in llm_map:
                llm_other = llm_map[profile.user_id]
                v_vec = llm_other.color_vec()

                character_score = cosine_sim(u_vec, v_vec)
                score_percentage = round(character_score * 100, 2)

                candidates.append({
                    "user_id": profile.user_id,
                    "name": profile.full_name,
                    "gender": profile.gender,
                    "location": profile.current_city,
                    "score_color": character_score,
                    "score_expect": 0,
                    "final_score": score_percentage,
                    "blue": llm_other.blue,
                    "green": llm_other.green,
                    "yellow": llm_other.yellow,
                    "red": llm_other.red,
                    "explanations": [],
                    "explanation_source": "character"
                })

        candidates.sort(key=lambda x: x["score_color"], reverse=True)
        print(f"🔍 DEBUG: Pure character matching found {len(candidates)} candidates")

        print("🔍 DEBUG: Candidate scores distribution:")
        score_ranges = {"90+": 0, "80-89": 0, "70-79": 0, "60-69": 0, "below_60": 0}
        for candidate in candidates:
            score = candidate["final_score"]
            if score >= 90:
                score_ranges["90+"] += 1
            elif score >= 80:
                score_ranges["80-89"] += 1
            elif score >= 70:
                score_ranges["70-79"] += 1
            elif score >= 60:
                score_ranges["60-69"] += 1
            else:
                score_ranges["below_60"] += 1

        for range_name, count in score_ranges.items():
            print(f"   {range_name}: {count} users")

        print("🔍 DEBUG: Top 10 candidate scores:")
        for i, candidate in enumerate(candidates[:10]):
            print(
                f"   {i+1}. {candidate['name']}: "
                f"raw={candidate['score_color']:.3f}, percentage={candidate['final_score']}%"
            )

        matches_by_range = {
            "90-100": [],
            "80-89": [],
            "70-79": [],
            "60-69": [],
            "below_60": []
        }

        for candidate in candidates:
            score_percentage = candidate["final_score"]

            if score_percentage >= 90:
                range_key = "90-100"
            elif score_percentage >= 80:
                range_key = "80-89"
            elif score_percentage >= 70:
                range_key = "70-79"
            elif score_percentage >= 60:
                range_key = "60-69"
            else:
                range_key = "below_60"

            matches_by_range[range_key].append(candidate)

        print("🔍 DEBUG: Range distribution after grouping:")
        for range_key, matches in matches_by_range.items():
            if matches:
                scores = [m["final_score"] for m in matches]
                print(f"   {range_key}: {len(matches)} users, scores: {min(scores):.1f}% - {max(scores):.1f}%")
            else:
                print(f"   {range_key}: 0 users")

        user = Users.query.filter_by(user_id=user_id).first()

        input_user = {
            "user_id": user_id,
            "role": "marriage",
            "name": user.name if user else "Unknown",
            "blue": base_llm.blue,
            "green": base_llm.green,
            "yellow": base_llm.yellow,
            "red": base_llm.red,
            "created_at": base_llm.created_at.isoformat() if base_llm.created_at else None,
        }

        print(f"✅ DEBUG: Returning {len(candidates)} pure character matches (NO EXPECTATION FILTERING)")

        return jsonify({
            "input_user": input_user,
            "matches": matches_by_range,
            "count": len(candidates),
            "mode": "character"
        })

    # 3) EXPECTATION + CHARACTER
    else:
        print("🎯 Using EXPECTATION + CHARACTER matching")

        expectation_matches = match_expectation_with_profiles(user_id)

        if not expectation_matches:
            return jsonify({"error": f"No matches found for user_id={user_id}"}), 404

        matches_by_range = {
            "90-100": [],
            "80-89": [],
            "70-79": [],
            "60-69": [],
            "below_60": []
        }

        for match in expectation_matches:
            score_percentage = match.get("overall_score", 0) * 100

            if score_percentage >= 90:
                range_key = "90-100"
            elif score_percentage >= 80:
                range_key = "80-89"
            elif score_percentage >= 70:
                range_key = "70-79"
            elif score_percentage >= 60:
                range_key = "60-69"
            else:
                range_key = "below_60"

            match_obj = {
                "user_id": match["user_id"],
                "name": match["name"],
                "gender": match.get("gender", ""),
                "city": match.get("location", ""),
                "final_score": round(score_percentage, 2),
                "score_expect": match.get("expectation_score", 0),
                "score_color": match.get("character_score", 0),
                "blue": 0,
                "green": 0,
                "yellow": 0,
                "red": 0,
                "explanations": [],
                "explanation_source": "expectation"
            }

            matches_by_range[range_key].append(match_obj)

        user = Users.query.filter_by(user_id=user_id).first()
        llm_data = LLMGeneratedQuestions.query.filter_by(user_id=user_id).first()

        input_user = {
            "user_id": user_id,
            "role": "marriage",
            "name": user.name if user else "Unknown",
            "blue": llm_data.blue if llm_data else 0,
            "green": llm_data.green if llm_data else 0,
            "yellow": llm_data.yellow if llm_data else 0,
            "red": llm_data.red if llm_data else 0,
            "created_at": llm_data.created_at.isoformat() if llm_data and llm_data.created_at else None,
        }

        print(f"✅ DEBUG: Returning {len(expectation_matches)} expectation + character matches")

        return jsonify({
            "input_user": input_user,
            "matches": matches_by_range,
            "count": len(expectation_matches),
            "mode": "expectation"
        })


@matching_bp.get("/compatibility-explanation")
@matching_bp.get("/api/compatibility-explanation")
def get_compatibility_explanation():
    user_id = request.args.get("user_id", type=int)
    target_user_id = request.args.get("target_user_id", type=int)
    mode = request.args.get("mode", "expectation-only")

    if not user_id or not target_user_id:
        return jsonify({"error": "user_id and target_user_id are required"}), 400

    try:
        # TAB 1 -> EXPECTATION ONLY
        if mode == "expectation-only":
            exp_user = fetch_expectation_data(user_id)
            profile_user = fetch_marriage_profile_data(target_user_id)

            explanations = generate_expectation_explanation(exp_user, profile_user)

            return jsonify({
                "mode": "expectation-only",
                "explanations": explanations,
                "source": "expectation-fallback"
            })

        # TAB 2 -> CHARACTER ONLY
        elif mode == "character":
            llm1 = LLMGeneratedQuestions.query.filter_by(user_id=user_id).first()
            llm2 = LLMGeneratedQuestions.query.filter_by(user_id=target_user_id).first()

            if not (llm1 and llm2):
                return jsonify({
                    "mode": "character",
                    "explanations": [
                        "Character analysis unavailable - no personality data found for one or both users."
                    ],
                    "source": "error"
                })

            u_vec = llm1.color_vec()
            v_vec = llm2.color_vec()

            try:
                print(f"🎯 Generating AI character analysis for users {user_id} and {target_user_id}...")
                character_explanations = generate_character_llm_explanation(u_vec, v_vec)
                source_type = "character-llm"

            except Exception as e:
                print(f"🔴 Character LLM failed, using fallback: {e}")

                try:
                    character_explanations = generate_character_fallback_explanation(u_vec, v_vec)
                    source_type = "character-fallback"
                    print("🟢 Character backend fallback worked")

                except Exception as fb_error:
                    print(f"🔴 Character fallback also failed: {fb_error}")

                    character_explanations = [
                        f"User {user_id} personality mix: Blue {u_vec[0]}, Green {u_vec[1]}, Yellow {u_vec[2]}, Red {u_vec[3]}",
                        f"User {target_user_id} personality mix: Blue {v_vec[0]}, Green {v_vec[1]}, Yellow {v_vec[2]}, Red {v_vec[3]}",
                        "Detailed AI character explanation is temporarily unavailable.",
                        "Basic personality summary has been returned instead."
                    ]
                    source_type = "character-basic-fallback"

            return jsonify({
                "mode": "character",
                "explanations": character_explanations,
                "source": source_type
            })

        # TAB 3 -> EXPECTATION + CHARACTER
        elif mode == "expectation":
            exp_user = fetch_expectation_data(user_id)
            profile_user = fetch_marriage_profile_data(target_user_id)

            expectation_part = generate_expectation_explanation(exp_user, profile_user)

            llm1 = LLMGeneratedQuestions.query.filter_by(user_id=user_id).first()
            llm2 = LLMGeneratedQuestions.query.filter_by(user_id=target_user_id).first()

            if llm1 and llm2:
                u_vec = llm1.color_vec()
                v_vec = llm2.color_vec()

                try:
                    character_explanations = generate_character_llm_explanation(u_vec, v_vec)
                    source_type = "character-llm"

                except Exception as e:
                    print(f"🔴 LLM failed, using backend fallback: {e}")

                    try:
                        character_explanations = generate_character_fallback_explanation(u_vec, v_vec)
                        source_type = "character-fallback"
                        print("🟢 Mixed-mode backend fallback worked")

                    except Exception as fb_error:
                        print(f"🔴 Mixed-mode fallback also failed: {fb_error}")
                        character_explanations = [
                            "Character insight is temporarily unavailable."
                        ]
                        source_type = "character-basic-fallback"
            else:
                character_explanations = ["Character analysis unavailable for this user."]
                source_type = "error"

            final_output = expectation_part + ["", "🧠 **AI Character Insights**"] + character_explanations

            return jsonify({
                "mode": "expectation",
                "explanations": final_output,
                "source": source_type
            })

        else:
            return jsonify({"error": "Invalid mode"}), 400

    except Exception as e:
        print(f"🔴 Error in compatibility explanation: {e}")
        traceback.print_exc()
        return jsonify({
            "explanations": [f"❌ Service temporarily unavailable: {str(e)}"],
            "source": "error"
        }), 500