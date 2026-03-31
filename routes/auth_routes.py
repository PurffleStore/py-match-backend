# auth_routes.py (with more debug logging)
# from flask import Blueprint, request, jsonify
# import pyodbc
# import traceback
# import os

# auth_bp = Blueprint('auth', __name__)
# print(f"✅ AUTH ROUTES: Blueprint '{auth_bp.name}' created")

from flask import Blueprint, request, jsonify
import traceback
import os

# Try to import pyodbc, but do not crash if it is missing
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError as e:
    pyodbc = None
    HAS_PYODBC = False
    print(f"❌ AUTH ROUTES: pyodbc is not available ({e}). Database functions will not work in this environment.")

auth_bp = Blueprint('auth', __name__)
print(f"✅ AUTH ROUTES: Blueprint '{auth_bp.name}' created")



def get_db_connection():
    if not HAS_PYODBC:
        # This exception will be caught where get_db_connection() is called
        raise RuntimeError("pyodbc is not installed or the ODBC driver is missing. Cannot connect to SQL Server.")

    # Read settings from environment variables
    SQL_DRIVER = os.getenv("PYMATCH_SQL_DRIVER", "ODBC Driver 17 for SQL Server")
    SQL_SERVER = os.getenv("PYMATCH_SQL_SERVER", r"DESKTOP-QBPLIVH")
    SQL_DB = os.getenv("PYMATCH_SQL_DB", "PyMatch")
    SQL_TRUSTED = os.getenv("PYMATCH_SQL_TRUSTED", "yes").lower()

    # Build connection string
    if SQL_TRUSTED == "yes":
        # Windows trusted connection (for local use)
        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DB};"
            f"Trusted_Connection=yes;"
        )
    else:
        # SQL username / password (for AWS RDS, Hugging Face)
        SQL_USER = os.getenv("PYMATCH_SQL_USER", "")
        SQL_PASSWORD = os.getenv("PYMATCH_SQL_PASSWORD", "")

        conn_str = (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DB};"
            f"UID={SQL_USER};"
            f"PWD={SQL_PASSWORD};"
        )

    # Basic debug (do not print password)
    print(f"🔗 AUTH ROUTES: Connecting to {SQL_SERVER}/{SQL_DB} with driver '{SQL_DRIVER}', trusted={SQL_TRUSTED}")

    return pyodbc.connect(conn_str)



@auth_bp.route('/signup', methods=['POST', 'OPTIONS'])
def signup():
    print(f"🎯 AUTH ROUTES: /signup endpoint called")
    
    if request.method == 'OPTIONS':
        print(f"🔄 AUTH ROUTES: Handling OPTIONS preflight request")
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')
        return response
    
    try:
        data = request.get_json(force=True) or {}
        print(f"🟢 AUTH ROUTES: Received signup request with data: {data}")
        
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:
            print(f"❌ AUTH ROUTES: Missing required fields")
            return jsonify({"success": False, "message": "Name, email, and password are required."}), 400

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            print(f"🟢 AUTH ROUTES: Checking if email '{email}' already exists...")

            # Check if email already exists
            cur.execute("SELECT user_id FROM Users WHERE email = ?", (email,))
            existing = cur.fetchone()
            if existing:
                print(f"❌ AUTH ROUTES: Email '{email}' already exists in database")
                return jsonify({"success": False, "message": "User already exists. Please sign in."}), 409

            # Use plain password (as per your original code)
            plain_password = password

            print(f"🟢 AUTH ROUTES: Inserting new user '{name}' with email '{email}'")

            # Insert into Users table with plain password
            cur.execute("""
                INSERT INTO Users (name, email, password)
                VALUES (?, ?, ?)
            """, (name, email, plain_password))
            conn.commit()

            # Fetch the newly inserted user_id
            cur.execute("SELECT @@IDENTITY AS user_id")
            row = cur.fetchone()
            user_id = row[0] if row else None
            
            print(f"✅ AUTH ROUTES: Successfully created user. User ID: {user_id}")

            conn.close()
            return jsonify({
                "success": True,
                "message": "Signup successful.",
                "user_id": user_id,
                "name": name,
                "email": email
            }), 201

        except pyodbc.Error as e:
            print(f"❌ AUTH ROUTES: Database Error: {e}")
            print(f"❌ AUTH ROUTES: SQL State: {e.sqlstate if hasattr(e, 'sqlstate') else 'N/A'}")
            print(f"❌ AUTH ROUTES: Error Code: {e.args[0] if e.args else 'N/A'}")
            return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

        except Exception as e:
            print(f"❌ AUTH ROUTES: Unexpected Error: {e}")
            traceback.print_exc()
            return jsonify({"success": False, "message": f"Unexpected error: {str(e)}"}), 500

    except Exception as e:
        print(f"❌ AUTH ROUTES: Outer exception: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    print(f"🎯 AUTH ROUTES: /login endpoint called")
    try:
        data = request.get_json(force=True) or {}
        print(f"🟢 AUTH ROUTES: Received login request with email: {data.get('email', 'not provided')}")
        
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            print(f"❌ AUTH ROUTES: Missing email or password")
            return jsonify({"success": False, "message": "Email and password are required."}), 400

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            print(f"🟢 AUTH ROUTES: Looking for user with email: {email}")
            cur.execute("SELECT user_id, name, email, password FROM Users WHERE email = ?", (email,))
            user = cur.fetchone()

            if not user:
                print(f"❌ AUTH ROUTES: User not found with email: {email}")
                return jsonify({"success": False, "message": "User not found."}), 404

            user_id, name, email, stored_password = user
            print(f"🟢 AUTH ROUTES: Found user ID: {user_id}, Name: {name}")

            # Use simple string comparison for plain text passwords
            if stored_password != password:
                print(f"❌ AUTH ROUTES: Password mismatch for user {user_id}")
                return jsonify({"success": False, "message": "Invalid password."}), 401

            print(f"✅ AUTH ROUTES: Successful login for user {user_id}")
            conn.close()
            return jsonify({
                "success": True,
                "message": "Login successful.",
                "user_id": user_id,
                "name": name,
                "email": email
            }), 200

        except pyodbc.Error as e:
            print(f"❌ AUTH ROUTES: Database Error: {e}")
            return jsonify({"success": False, "message": f"Database error: {e}"}), 500

        except Exception as e:
            print(f"❌ AUTH ROUTES: Unexpected Error: {e}")
            traceback.print_exc()
            return jsonify({"success": False, "message": f"Unexpected error: {e}"}), 500

    except Exception as e:
        print(f"❌ AUTH ROUTES: Outer exception: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@auth_bp.route('/test', methods=['GET'])
def test():
    print("✅ AUTH ROUTES: /test endpoint hit!")
    return jsonify({"message": "Auth routes are working!", "status": "ok", "blueprint": auth_bp.name}), 200