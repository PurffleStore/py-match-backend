# routes/profile_routes.py
from flask import Blueprint, request, jsonify
import pyodbc
import json
# from database import get_db_connection, row_to_dict
from .auth_routes import get_db_connection   # reuse the working connection logic
from database import row_to_dict            # still use row_to_dict from database.py
from models import Marriage, LLMGeneratedQuestions
from config import APP_ENV

profiles_bp = Blueprint('profiles', __name__)

@profiles_bp.route('/api/questions/select-role', methods=['POST'])
def select_role():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")
    role_name = data.get("role_name")
    assigned_at = data.get("assigned_at")  # ISO or None

    # Check if user_id and role_name are provided
    if not user_id or not role_name:
        return jsonify({"error": "User ID and role name are required."}), 400

    try:
        # Check if user_id exists in the Users table
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Users WHERE user_id = ?", (user_id,))
        user_exists = cur.fetchone()[0]

        if user_exists == 0:
            return jsonify({"error": "User ID does not exist in the Users table."}), 404

        # Proceed with inserting into UserRoles
        cur.execute("""
            INSERT INTO UserRoles (user_id, role_name, assigned_at)
            VALUES (?, ?, ?)
        """, (user_id, role_name, assigned_at))
        conn.commit()

        return jsonify({"message": "Role assigned successfully."}), 201

    except pyodbc.Error as e:
        # Handle database error, including foreign key constraint violations
        if "foreign key" in str(e).lower():
            return jsonify({"error": "Foreign key violation: User ID not found."}), 400
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@profiles_bp.route('/api/questions/marriage', methods=['GET'])
def get_questions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT question, options, input_type, column_key, category
            FROM RoleQuestions
            WHERE role_name = 'marriage'
            ORDER BY id
        """)
        rows = cur.fetchall()
        out = []
        for r in rows:
            label = r[0]
            options = (r[1].split(",") if r[1] else [])
            input_type = r[2]
            column_key = r[3]
            category = r[4]
            out.append({
                "label": label,
                "options": options,
                "input_type": input_type,
                "column_key": column_key,
                "category": category
            })
        return jsonify(out), 200
    except pyodbc.Error as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except: pass

@profiles_bp.route('/api/questions/submit-answers/marriage', methods=['POST'])
def submit_answers():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID is required."}), 400

    role_fields = {
            "marriage": [
                "full_name", "date_of_birth", "gender", "current_city", "marital_status",
                "education_level", "employment_status", "number_of_siblings", "family_type",
                "hobbies_interests", "conflict_approach", "financial_style", "income_range",
                "relocation_willingness", "height", "skin_tone", "languages_spoken", "country",
                "blood_group", "religion", "dual_citizenship", "siblings_position",
                "parents_living_status", "live_with_parents", "support_parents_financially",
                "family_communication_frequency", "food_preference", "smoking_habit",
                "alcohol_habit", "daily_routine", "fitness_level", "own_pets",
                "travel_preference", "relaxation_mode", "job_role", "work_experience_years",
                "career_aspirations", "field_of_study", "remark", "children_timeline",
                "open_to_adoption", "deal_breakers", "other_non_negotiables",
                "health_constraints", "live_with_inlaws"
                # Note: "created_at" is excluded (auto-generated)
            ]
        }

    # Validate all required fields are present
    for f in role_fields["marriage"]:
        if f not in data:
            return jsonify({"error": f"{f} is required."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        table_name = "Marriage"
        
        # Build INSERT query without created_at
        columns = ["user_id"] + role_fields["marriage"]
        placeholders = ", ".join(["?"] * len(columns))
        col_str = ", ".join([f"[{c}]" for c in columns])
        
        query = f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})"

        values = [user_id]
        for f in role_fields["marriage"]:
            val = data.get(f)
                        # Handle radio button values (convert 1/0 to yes/no)
            if f in ["dual_citizenship", "live_with_parents", "support_parents_financially", "own_pets"]:
                if val == 1 or val == "1" or val is True:
                    val = "Yes"
                elif val == 0 or val == "0" or val is False:
                    val = "No"
                # If it's already "yes" or "no", leave it as is
                elif val not in ["Yes", "No"]:
                    val = "No"  # default to "no" if invalid value
            # Handle list values (multiselect)
            if isinstance(val, list):
                val = ", ".join([str(v) for v in val])

            # Convert to string or None
            if val is None:
                val = None
            else:
                val = str(val)

            values.append(val)

        print(f"DEBUG: Executing query: {query}")
        print(f"DEBUG: Values: {values}")

        cur.execute(query, values)
        conn.commit()

        return jsonify({"message": "Marriage record added successfully."}), 201

    except pyodbc.Error as e:
        print(f"Database Error: {e}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@profiles_bp.route('/api/questions/existing-profile/<role>/<int:user_id>', methods=['GET'])
def get_existing_profile(role: str, user_id: int):
    """Get existing profile data for a user"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Determine table based on role
        table_map = {
            "marriage": "Marriage",
            "interview": "Interview", 
            "partnership": "Partnership"
        }
        
        table_name = table_map.get(role.lower())
        if not table_name:
            return jsonify({"error": "Invalid role"}), 400
        
        cur.execute(f"""
            SELECT TOP 1 * FROM {table_name} 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user_id,))
        
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "No profile found"}), 404
            
        # Convert row to dict
        profile = row_to_dict(cur, row)
        
        # 🚨 CRITICAL: Clean up data for radio buttons
        # Ensure radio button values are clean strings that match option values
        for key, value in profile.items():
            if value is not None:
                # Convert to string and trim for consistency
                if isinstance(value, bool):
                    profile[key] = "Yes" if value else "No"
                elif isinstance(value, (int, float)):
                    profile[key] = str(value)
                elif isinstance(value, str):
                    profile[key] = value.strip()
        
        print(f"🟢 DEBUG: Returning cleaned profile data for user {user_id}")
        return jsonify(profile), 200
        
    except Exception as e:
        print(f"Error fetching existing profile: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@profiles_bp.route('/api/questions/update-answers/<role>', methods=['PUT'])
def update_answers(role: str):
    """Update existing profile answers"""
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")
    
    if not user_id:
        return jsonify({"error": "User ID is required."}), 400

    role_fields = {
            "marriage": [
                "full_name", "date_of_birth", "gender", "current_city", "marital_status",
                "education_level", "employment_status", "number_of_siblings", "family_type",
                "hobbies_interests", "conflict_approach", "financial_style", "income_range",
                "relocation_willingness", "height", "skin_tone", "languages_spoken", "country",
                "blood_group", "religion", "dual_citizenship", "siblings_position",
                "parents_living_status", "live_with_parents", "support_parents_financially",
                "family_communication_frequency", "food_preference", "smoking_habit",
                "alcohol_habit", "daily_routine", "fitness_level", "own_pets",
                "travel_preference", "relaxation_mode", "job_role", "work_experience_years",
                "career_aspirations", "field_of_study", "remark", "children_timeline",
                "open_to_adoption", "deal_breakers", "other_non_negotiables",
                "health_constraints", "live_with_inlaws"
                # Note: "created_at" is excluded (auto-generated)
            ]
        }

    if role not in role_fields:
        return jsonify({"error": f"Invalid role: {role}"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        table_name = "Marriage" if role == "marriage" else role.capitalize()
        
        # Build UPDATE query - only include fields that are present in data
        set_parts = []
        values = []
        
        for field in role_fields[role]:
            if field in data:
                set_parts.append(f"{field} = ?")
                val = data.get(field)
                # Handle radio button values (convert 1/0 to yes/no)
                if field in ["dual_citizenship", "live_with_parents", "support_parents_financially", "own_pets"]:
                    if val == 1 or val == "1" or val is True:
                        val = "Yes"
                    elif val == 0 or val == "0" or val is False:
                        val = "No"
                    # If it's already "Yes" or "no", leave it as is
                    elif val not in ["Yes", "No"]:
                        val = "No"  # default to "no" if invalid value
                # Handle list values (multiselect)
                if isinstance(val, list):
                    val = ", ".join([str(v) for v in val])

                # Convert to string or None
                if val is None:
                    val = None
                else:
                    val = str(val)

                values.append(val)

        if not set_parts:
            return jsonify({"error": "No valid fields to update"}), 400

        # Add user_id for WHERE clause
        values.append(user_id)
        
        set_clause = ", ".join(set_parts)
        query = f"UPDATE {table_name} SET {set_clause} WHERE user_id = ?"

        print(f"DEBUG: Executing update query: {query}")
        print(f"DEBUG: Values: {values}")

        cur.execute(query, values)
        conn.commit()

        # Check if any row was updated
        if cur.rowcount == 0:
            return jsonify({"error": "No profile found to update"}), 404

        return jsonify({"message": "Profile updated successfully."}), 200

    except pyodbc.Error as e:
        print(f"Database Error: {e}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected Error: {e}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@profiles_bp.route('/api/marriage-profile/<int:user_id>', methods=['GET'])
def get_marriage_profile(user_id: int):
    """Get marriage profile by user_id"""
    try:
        profile = Marriage.query.filter_by(user_id=user_id) \
            .order_by(Marriage.created_at.desc()) \
            .first()

        if profile is None:
            return jsonify({"error": "Marriage profile not found"}), 404

        result = {}
        for column in Marriage.__table__.columns:
            value = getattr(profile, column.name)

            # optional: convert datetime to string
            if hasattr(value, "isoformat"):
                value = value.isoformat()

            result[column.name] = value

        return jsonify(result), 200

    except Exception as e:
        print(f"Error fetching marriage profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# @profiles_bp.route('/api/marriage-profile/<int:user_id>', methods=['GET'])
# def get_marriage_profile(user_id: int):
#     """Get marriage profile by user_id"""
#     conn = None
#     try:
#         conn = get_db_connection()
#         cur = conn.cursor()

#         if APP_ENV == "local":
#             cur.execute("""
#                 SELECT * FROM Marriage
#                 WHERE user_id = ?
#                 ORDER BY created_at DESC
#             """, (user_id,))
#         else:
#             cur.execute("""
#                 SELECT * FROM Marriage
#                 WHERE user_id = %s
#                 ORDER BY created_at DESC
#             """, (user_id,))

#         row = cur.fetchone()
#         if row is None:
#             return jsonify({"error": "Marriage profile not found"}), 404

#         profile = row_to_dict(cur, row)
#         return jsonify(profile), 200

#     except Exception as e:
#         print(f"Error fetching marriage profile: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

#     finally:
#         try:
#             if conn:
#                 conn.close()
#         except:
#             pass

# @profiles_bp.route('/api/marriage-profile/<int:user_id>', methods=['GET'])
# def get_marriage_profile(user_id: int):
#     """Get marriage profile by user_id"""
#     try:
#         conn = get_db_connection()
#         cur = conn.cursor()

#         cur.execute("""
#             SELECT * FROM Marriage
#             WHERE user_id = ?
#             ORDER BY created_at DESC
#         """, (user_id,))

#         row = cur.fetchone()
#         if row is None:
#             return jsonify({"error": "Marriage profile not found"}), 404

#         # Convert row to dict
#         profile = row_to_dict(cur, row)

#         return jsonify(profile), 200

#     except Exception as e:
#         print(f"Error fetching marriage profile: {e}")
#         return jsonify({"error": str(e)}), 500
#     finally:
#         try:
#             conn.close()
#         except:
#             pass
# @profiles_bp.route('/api/check-marriage-profile/<int:user_id>', methods=['GET'])
# def check_marriage_profile(user_id: int):
#     """Check if marriage profile exists for user"""
#     try:
#         exists = Marriage.query.filter_by(user_id=user_id).first() is not None
#         return jsonify({"exists": exists}), 200

#     except Exception as e:
#         print(f"Error checking marriage profile: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

@profiles_bp.route('/api/check-marriage-profile/<int:user_id>', methods=['GET'])
def check_marriage_profile(user_id: int):
    """Check if marriage profile exists for user"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if APP_ENV == "local":
            cur.execute("""
                SELECT COUNT(*) as count
                FROM Marriage
                WHERE user_id = ?
            """, (user_id,))
        else:
            cur.execute("""
                SELECT COUNT(*) as count
                FROM Marriage
                WHERE user_id = %s
            """, (user_id,))

        row = cur.fetchone()

        if APP_ENV == "local":
            exists = row[0] > 0 if row else False
        else:
            if isinstance(row, dict):
                exists = row.get("count", 0) > 0
            else:
                exists = row[0] > 0 if row else False

        return jsonify({"exists": exists}), 200

    except Exception as e:
        print(f"Error checking marriage profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
@profiles_bp.route('/api/check-assessment/<int:user_id>', methods=['GET'])
def check_assessment(user_id: int):
    """Check if assessment is completed for user"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if APP_ENV == "local":
            cur.execute("""
                SELECT COUNT(*) as count
                FROM LLMGeneratedQuestions
                WHERE user_id = ?
            """, (user_id,))
        else:
            cur.execute("""
                SELECT COUNT(*) as count
                FROM LLMGeneratedQuestions
                WHERE user_id = %s
            """, (user_id,))

        row = cur.fetchone()

        if APP_ENV == "local":
            exists = row[0] > 0 if row else False
        else:
            if isinstance(row, dict):
                exists = row.get("count", 0) > 0
            else:
                exists = row[0] > 0 if row else False

        return jsonify({"exists": exists}), 200

    except Exception as e:
        print(f"Error checking assessment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


@profiles_bp.route('/api/check-assessment-completion/<int:user_id>', methods=['GET'])
def check_assessment_completion(user_id: int):
    """Check if user has already completed the assessment"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if APP_ENV == "local":
            cur.execute("""
                SELECT COUNT(*) as count
                FROM LLMGeneratedQuestions
                WHERE user_id = ?
                  AND (blue > 0 OR green > 0 OR yellow > 0 OR red > 0)
            """, (user_id,))
        else:
            cur.execute("""
                SELECT COUNT(*) as count
                FROM LLMGeneratedQuestions
                WHERE user_id = %s
                  AND (blue > 0 OR green > 0 OR yellow > 0 OR red > 0)
            """, (user_id,))

        row = cur.fetchone()

        if APP_ENV == "local":
            count = row[0] if row else 0
        else:
            if isinstance(row, dict):
                count = row.get("count", 0)
            else:
                count = row[0] if row else 0

        has_taken_assessment = count > 0

        print(f"🔍 Assessment check for user {user_id}: {has_taken_assessment}")

        return jsonify({
            "has_taken_assessment": has_taken_assessment,
            "message": "User has already taken assessment" if has_taken_assessment else "User can take assessment"
        }), 200

    except Exception as e:
        print(f"Error checking assessment completion: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


