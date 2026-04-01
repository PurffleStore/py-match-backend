APP_BUILD = "HF-BUILD-2025-12-15-01"
print("✅ RUNNING APP BUILD:", APP_BUILD, "FILE:", __file__)

# app.py (HF-safe + corrected health + debug routes)
import os
import datetime
import traceback

from flask import Flask, jsonify, request
from flask_cors import CORS

# FAISS / knowledge
from faiss_service import FAISS_INDEX, TEXT_CHUNKS, HAS_FAISS, knowledge

# Config
from config import (
    APP_ENV,
    SQL_DRIVER,
    SQL_SERVER,
    SQL_DB,
    SQL_TRUSTED,
    SQL_USER,
    SQL_PASSWORD,
    SQL_PORT,
    SQL_ENCRYPT,
    SQL_TRUSTCERT,
    PROGRESS_TBL,
)

from models import db

# LLM / chain imports (safe if module not present)
try:
    from llm_service import CHAIN_BATCH
    try:
        from llm_service import llm_chain
    except ImportError:
        llm_chain = None
except ImportError:
    CHAIN_BATCH = None
    llm_chain = None


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    print("🚀 DEBUG: Starting app creation...")
    print(f"🚀 DEBUG: APP_ENV = {APP_ENV}")
    print(f"🚀 DEBUG: SQL_SERVER = {SQL_SERVER}")
    print(f"🚀 DEBUG: SQL_DB = {SQL_DB}")

    # ----------------------------
    # Request logging
    # ----------------------------
    @app.before_request
    def log_request_info():
        print(f"\n{'=' * 60}")
        print("📥 INCOMING REQUEST:")
        print(f"   Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Method: {request.method}")
        print(f"   Path: {request.path}")
        print(f"   URL: {request.url}")
        print(f"   Remote Address: {request.remote_addr}")
        if request.user_agent:
            print(f"   User Agent: {request.user_agent.string[:80]}...")
        print(f"   Referrer: {request.referrer}")
        print(f"{'=' * 60}")

    # ----------------------------
    # DB init
    # ----------------------------
    try:
        from database import init_database
        init_database(app)
        print("✅ DEBUG: Database initialized successfully")
    except Exception as e:
        print(f"❌ DEBUG: Failed to initialize database: {e}")
        traceback.print_exc()

    # ----------------------------
    # Blueprint import + register (HF safe)
    # ----------------------------
    blueprint_status = {}

    try:
        import routes as routes_module
        print("✅ DEBUG: Imported routes module")

        # Get blueprints safely (None means missing)
        candidates = [
            ("auth_bp", getattr(routes_module, "auth_bp", None), "/api"),
            ("profiles_bp", getattr(routes_module, "profiles_bp", None), None),
            ("expectations_bp", getattr(routes_module, "expectations_bp", None), None),
            ("matching_bp", getattr(routes_module, "matching_bp", None), "/api"),
            ("llm_bp", getattr(routes_module, "llm_bp", None), None),
        ]

        print(
            "✅ DEBUG: Blueprint objects (None means failed):",
            [bp.name if bp else None for _, bp, _ in candidates],
        )

        for name, bp, prefix in candidates:
            if bp is None:
                blueprint_status[name] = "MISSING (import failed or blueprint not created)"
                print(f"⚠️  DEBUG: Skipping {name} because it is None")
                continue

            try:
                if prefix:
                    app.register_blueprint(bp, url_prefix=prefix)
                else:
                    app.register_blueprint(bp)

                blueprint_status[name] = f"REGISTERED (name={bp.name}, prefix={prefix})"
                print(f"✅ DEBUG: Registered {name} as '{bp.name}' with prefix={prefix}")
            except Exception as reg_err:
                blueprint_status[name] = f"FAILED TO REGISTER: {reg_err}"
                print(f"❌ DEBUG: Failed to register {name}: {reg_err}")
                traceback.print_exc()

    except Exception as e:
        print(f"❌ DEBUG: Failed to import routes or register blueprints: {e}")
        traceback.print_exc()

    # ------------------------------------------------------------------
    # Debug endpoints (always available)
    # ------------------------------------------------------------------
    @app.get("/api/_routes")
    @app.get("/debug/routes")
    def list_routes():
        routes_list = []
        for rule in app.url_map.iter_rules():
            routes_list.append(
                {
                    "endpoint": rule.endpoint,
                    "methods": sorted(list(rule.methods)),
                    "rule": str(rule),
                }
            )

        has_double_api = any(r["rule"].startswith("/api/api/") for r in routes_list)

        return jsonify(
            {
                "count": len(routes_list),
                "has_double_api_prefix": has_double_api,
                "routes": sorted(routes_list, key=lambda x: x["rule"]),
            }
        )

    # ------------------------------------------------------------------
    # Health endpoint (both /health and /api/health to avoid breaking clients)
    # ------------------------------------------------------------------
    @app.get("/health")
    @app.get("/api/health")
    def health():
        # LLM mode
        llm_mode = "offline-fallback"
        try:
            if CHAIN_BATCH is not None:
                llm_mode = "openai"
        except Exception:
            pass

        # FAISS status
        faiss_chunks = len(TEXT_CHUNKS) if TEXT_CHUNKS is not None else 0
        faiss_loaded = bool(HAS_FAISS and FAISS_INDEX is not None and faiss_chunks > 0)

        # Knowledge base status
        if knowledge is not None and hasattr(knowledge, "indices"):
            knowledge_indices_count = len(getattr(knowledge, "indices", []))
            knowledge_loaded = knowledge_indices_count > 0
        else:
            knowledge_indices_count = 0
            knowledge_loaded = False

        return jsonify(
            {
                "status": "ok",
                "environment": APP_ENV,  # keep this line (as you requested)
                "llm": llm_mode,
                "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
                "db": {
                    "server": SQL_SERVER,
                    "database": SQL_DB,
                    "table": PROGRESS_TBL,
                },
                "faiss_available": HAS_FAISS,
                "faiss_loaded": faiss_loaded,
                "faiss_chunks": faiss_chunks,
                "knowledge_base_loaded": knowledge_loaded,
                "knowledge_indices": knowledge_indices_count,
                "blueprints": blueprint_status,
            }
        )

    # ------------------------------------------------------------------
    # Home endpoint
    # ------------------------------------------------------------------
    @app.get("/")
    def home():
        return jsonify(
            {
                "message": "Unified Py-Match Service (FAISS-enabled)",
                "try": [
                    "GET  /health",
                    "GET  /api/health",
                    "GET  /api/_routes",
                    "GET  /debug/routes",
                    "POST /api/signup",
                    "POST /api/login",
                    "GET  /api/questions/marriage",
                    "GET  /api/questions/existing-profile/marriage/<user_id>",
                    "GET  /api/expectation-questions",
                    "GET  /api/existing-preferences/<user_id>",
                    "POST /api/questions/submit-answers/<role>",
                    "POST /llm/start   (body: { user_id, role, n_questions, batch_size })",
                    "POST /llm/next    (body: { session_id, selected_color })",
                    "GET  /api/match/<user_id> (query: ?role=<role>&limit=<num>)",
                ],
            }
        )

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Endpoint not found", "path": request.path}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return (
            jsonify(
                {
                    "error": "Method not allowed",
                    "message": f"Method {request.method} not allowed for {request.path}",
                    "allowed_methods": (
                        error.valid_methods if hasattr(error, "valid_methods") else []
                    ),
                }
            ),
            405,
        )

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app

app = create_app()
if __name__ == "__main__":
    

    print(f"\n{'=' * 60}")
    print("🚀 Flask server starting...")
    print(f"{'=' * 60}")

    app.run(host="0.0.0.0", port=5000, debug=True)
