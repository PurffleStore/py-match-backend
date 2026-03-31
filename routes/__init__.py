# # routes/__init__.py
# from .auth_routes import auth_bp
# from .profile_routes import profiles_bp
# from .expectation_routes import expectations_bp
# from .matching_routes import matching_bp
# from .llm_routes import llm_bp

# __all__ = ['auth_bp', 'profiles_bp', 'expectations_bp', 'matching_bp', 'llm_bp']


# routes/__init__.py

# Always try to import auth_routes (we need login)
try:
    from .auth_routes import auth_bp
except Exception as e:
    auth_bp = None
    print(f"❌ ROUTES: Failed to import auth_routes: {e}")

# Other blueprints are optional – do not stop the app if one fails
try:
    from .profile_routes import profiles_bp
except Exception as e:
    profiles_bp = None
    print(f"❌ ROUTES: Failed to import profile_routes: {e}")

try:
    from .expectation_routes import expectations_bp
except Exception as e:
    expectations_bp = None
    print(f"❌ ROUTES: Failed to import expectation_routes: {e}")

try:
    from .matching_routes import matching_bp
except Exception as e:
    matching_bp = None
    print(f"❌ ROUTES: Failed to import matching_routes: {e}")

try:
    from .llm_routes import llm_bp
except Exception as e:
    llm_bp = None
    print(f"❌ ROUTES: Failed to import llm_routes: {e}")

__all__ = ['auth_bp', 'profiles_bp', 'expectations_bp', 'matching_bp', 'llm_bp']
