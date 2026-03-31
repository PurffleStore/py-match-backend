# routes/expectation_routes.py
from flask import Blueprint, request, jsonify
import pyodbc
import json
# from database import get_db_connection, row_to_dict
from .auth_routes import get_db_connection   # use the working DB connection
from database import row_to_dict            # still use row_to_dict from database.py

expectations_bp = Blueprint('expectations', __name__)

@expectations_bp.route('/api/existing-preferences/<int:user_id>', methods=['GET'])
def get_existing_preferences(user_id: int):
    """Get existing preferences data for a user"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT TOP 1 * FROM ExpectationResponse 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user_id,))
        
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "No preferences found"}), 404
            
        # Convert row to dict
        preferences = row_to_dict(cur, row)
        
        # Process multi-select fields that are stored as comma-separated strings
        # Get multi_select question keys from ExpectationQuestions
        cur.execute("SELECT column_key FROM ExpectationQuestions WHERE input_type = 'multi_select'")
        multi_select_keys = [row[0] for row in cur.fetchall()]
        
        for key in multi_select_keys:
            if key in preferences and preferences[key]:
                # Convert comma-separated string back to array
                if isinstance(preferences[key], str):
                    preferences[key] = [item.strip() for item in preferences[key].split(",") if item.strip()]
        
        return jsonify(preferences), 200
        
    except Exception as e:
        print(f"Error fetching existing preferences: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@expectations_bp.route('/api/update-preferences/<int:user_id>', methods=['PUT'])
def update_preferences(user_id: int):
    """Update existing preferences"""
    data = request.get_json(force=True) or {}
    
    if not user_id:
        return jsonify({"error": "User ID is required."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        print("🟢 DEBUG UPDATE: Incoming data keys ->", list(data.keys()))
        
        # 🚨 CRITICAL FIX: Handle _mandatory_fields FIRST
        mandatory_fields = data.get('_mandatory_fields', {})
        print("🎯 DEBUG UPDATE: Mandatory fields received:", mandatory_fields)
        
        # Build SET clause for update
        set_parts = []
        values = []
        
        # Handle _mandatory_fields - convert to JSON string
        if mandatory_fields:
            set_parts.append('_mandatory_fields = ?')
            if isinstance(mandatory_fields, dict):
                mandatory_json = json.dumps(mandatory_fields, ensure_ascii=False)
            else:
                mandatory_json = str(mandatory_fields)
            values.append(mandatory_json)
            print("✅ DEBUG UPDATE: Adding _mandatory_fields to update:", mandatory_json)

        # 🚨 CRITICAL: Field name mapping from frontend to database
        field_mapping = {
            'pref_live_with_inlaws': 'live_with_inlaws',
            'accept_financial_support_to_parents': 'financial_support_to_parents'
        }

        # Define all valid ExpectationResponse fields
        valid_fields = [
            'pref_age_range', 'pref_height_range', 'pref_current_city', 'pref_countries',
            'pref_languages', 'health_constraints', 'pref_diet', 'accept_smoking',
            'accept_alcohol', 'pref_fitness', 'pref_family_type', 'live_with_inlaws',
            'children_timeline', 'open_to_adoption', 'pref_conflict_approach',
            'pref_financial_style', 'religion_alignment', 'pref_shared_hobbies',
            'travel_pref', 'pet_pref', 'pref_income_range', 'deal_breakers',
            'other_non_negotiables', 'pref_education_level', 'pref_employment_status',
            'expectation_summary', 'skin_tone', 'marital_status', 'daily_routine',
            'family_communication_frequency', 'relaxation_mode', 'pref_partner_relocation',
            'financial_support_to_parents', 'pref_career_aspirations', 'pref_live_with_parents'
        ]
        
        # Get input types from ExpectationQuestions
        cur.execute("SELECT column_key, input_type FROM ExpectationQuestions")
        field_types = {row[0]: row[1] for row in cur.fetchall()}
        
        # Process all fields
        for key in valid_fields:
            # 🚨 CRITICAL: Check if we need to map the field name
            db_field_name = field_mapping.get(key, key)
            
            if key in data and key != 'user_id' and key != '_mandatory_fields':
                value = data[key]
                field_type = field_types.get(key, 'text')
                print(f"🟡 Processing update field {key} -> {db_field_name} (type: {field_type}): {value}")
                
                if field_type == 'multi_select' and isinstance(value, list):
                    clean_values = []
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            clean_item = item.strip()
                            clean_item = clean_item.replace('[', '').replace(']', '').replace('"', '').strip()
                            if clean_item and clean_item not in clean_values:
                                clean_values.append(clean_item)
                    
                    if clean_values:
                        final_value = ", ".join(clean_values)
                        print(f"🟢 Converted multi_select array to string: '{final_value}'")
                        set_parts.append(f"{db_field_name} = ?")  # 🚨 Use mapped field name
                        values.append(final_value)
                    else:
                        set_parts.append(f"{db_field_name} = ?")  # 🚨 Use mapped field name
                        values.append("")
                        
                elif field_type == 'multi_select' and isinstance(value, str):
                    clean_value = value.strip()
                    clean_value = clean_value.replace('[', '').replace(']', '').replace('"', '').strip()
                    if clean_value.startswith(',') or clean_value.endswith(','):
                        clean_value = clean_value.strip(',')
                    
                    print(f"🟢 Cleaning multi_select string: '{clean_value}'")
                    set_parts.append(f"{db_field_name} = ?")  # 🚨 Use mapped field name
                    values.append(clean_value)
                    
                elif value is not None:
                    final_value = str(value).strip() if isinstance(value, str) else value
                    print(f"🟢 Storing single value: '{final_value}'")
                    set_parts.append(f"{db_field_name} = ?")  # 🚨 Use mapped field name
                    values.append(final_value)
                else:
                    # Handle empty values
                    set_parts.append(f"{db_field_name} = ?")  # 🚨 Use mapped field name
                    values.append("")

        if not set_parts and not mandatory_fields:
            return jsonify({"error": "No valid fields to update"}), 400

        # Add user_id for WHERE clause
        values.append(user_id)
        
        set_clause = ", ".join(set_parts)
        query = f"UPDATE ExpectationResponse SET {set_clause} WHERE user_id = ?"
        
        print(f"🟢 DEBUG UPDATE: Executing query: {query}")
        print(f"🟢 DEBUG UPDATE: Values: {values}")

        cur.execute(query, values)
        conn.commit()

        # Check if any row was updated
        if cur.rowcount == 0:
            print("⚠️ WARNING: No rows were updated - user might not exist")
            return jsonify({"error": "No preferences found to update"}), 404

        print(f"✅ SUCCESS: Updated {cur.rowcount} row(s) for user {user_id}")
        return jsonify({"message": "Preferences updated successfully."}), 200

    except Exception as e:
        print(f"🔴 Error updating preferences: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@expectations_bp.route('/api/check-mandatory-fields/<int:user_id>', methods=['GET'])
def check_mandatory_fields(user_id: int):
    """Check current mandatory fields in database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT user_id, _mandatory_fields 
            FROM ExpectationResponse 
            WHERE user_id = ?
        """, (user_id,))
        
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "No preferences found for user"}), 404
            
        result = {
            "user_id": row[0],
            "_mandatory_fields": row[1],
            "_mandatory_fields_type": str(type(row[1])),
            "exists_in_db": row[1] is not None
        }
        
        print("🔍 CHECK MANDATORY FIELDS:", result)
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error checking mandatory fields: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@expectations_bp.route('/api/expectation-questions', methods=['GET'])
def get_expectation_questions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, question, options, input_type, column_key, category
            FROM ExpectationQuestions
            ORDER BY id
        """)
        rows = cur.fetchall()

        out = []
        for r in rows:
            out.append({
                "id": r[0],
                "question": r[1],
                "options": (r[2].split(",") if r[2] else []),
                "input_type": r[3],
                "column_key": r[4],
                "category": r[5]
            })
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try: conn.close()
        except: pass

@expectations_bp.route('/api/expectation-response', methods=['POST'])
def save_expectation_response():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get valid keys from ExpectationQuestions AND ExpectationResponse model
        cur.execute("SELECT column_key, input_type FROM ExpectationQuestions")
        valid_fields = {row[0]: row[1] for row in cur.fetchall()}
        
        # 🚨 CRITICAL FIX: Add all ExpectationResponse model fields
        expectation_model_fields = [
                    'pref_age_range', 'pref_height_range', 'pref_current_city', 'pref_countries',
                    'pref_languages', 'health_constraints', 'pref_diet', 'accept_smoking',
                    'accept_alcohol', 'pref_fitness', 'pref_family_type', 'live_with_inlaws',  # 🚨 CHANGED: Remove 'pref_' prefix
                    'children_timeline', 'open_to_adoption', 'pref_conflict_approach',
                    'pref_financial_style', 'religion_alignment', 'pref_shared_hobbies',
                    'travel_pref', 'pet_pref', 'pref_income_range', 'deal_breakers',
                    'other_non_negotiables', 'pref_education_level', 'pref_employment_status',
                    'expectation_summary', '_mandatory_fields', 'skin_tone', 'marital_status',
                    'daily_routine', 'family_communication_frequency', 'relaxation_mode',
                    'pref_partner_relocation', 'financial_support_to_parents',  # 🚨 CHANGED: Remove 'accept_' prefix
                    'pref_career_aspirations', 'pref_live_with_parents'
                ]
        
        # Add model fields to valid_fields (default to 'text' input type if not in questions)
        for field in expectation_model_fields:
            if field not in valid_fields:
                valid_fields[field] = 'text'  # default type

        print("🟢 DEBUG: Valid fields ->", list(valid_fields.keys()))
        print("🟢 DEBUG: Incoming data keys ->", list(data.keys()))

        cols, vals = [], []
        
        # 🚨 CRITICAL: Handle _mandatory_fields FIRST
        mandatory_fields = data.get('_mandatory_fields', {})
        if mandatory_fields:
            cols.append('_mandatory_fields')
            if isinstance(mandatory_fields, dict):
                mandatory_json = json.dumps(mandatory_fields, ensure_ascii=False)
                vals.append(mandatory_json)
            else:
                vals.append(str(mandatory_fields))
            print("✅ DEBUG: Added _mandatory_fields:", mandatory_fields)

        # Process all other fields
        for key, field_type in valid_fields.items():
            if key in data and key != 'user_id' and key != '_mandatory_fields':
                value = data[key]
                print(f"🟡 Processing field {key} (type: {field_type}): {value}")
                
                if value is None or value == '':
                    # Skip empty values
                    continue
                    
                if field_type == 'multi_select' and isinstance(value, list):
                    # Clean array data
                    clean_values = []
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            clean_item = item.strip()
                            clean_item = clean_item.replace('[', '').replace(']', '').replace('"', '').strip()
                            if clean_item and clean_item not in clean_values:
                                clean_values.append(clean_item)
                    
                    if clean_values:
                        final_value = ", ".join(clean_values)
                        print(f"🟢 Converted multi_select array to string: '{final_value}'")
                        cols.append(key)
                        vals.append(final_value)
                    else:
                        # Skip empty arrays
                        continue
                        
                elif field_type == 'multi_select' and isinstance(value, str):
                    # Clean string data
                    clean_value = value.strip()
                    clean_value = clean_value.replace('[', '').replace(']', '').replace('"', '').strip()
                    if clean_value.startswith(',') or clean_value.endswith(','):
                        clean_value = clean_value.strip(',')
                    
                    if clean_value:
                        print(f"🟢 Cleaning multi_select string: '{clean_value}'")
                        cols.append(key)
                        vals.append(clean_value)
                    else:
                        continue
                        
                else:
                    # For single values
                    final_value = str(value).strip() if isinstance(value, str) else value
                    if final_value:  # Only add non-empty values
                        print(f"🟢 Storing single value: '{final_value}'")
                        cols.append(key)
                        vals.append(final_value)

        if not cols:
            return jsonify({"error": "No valid fields found in request"}), 400

        # Build INSERT query
        placeholders = ", ".join(["?"] * (len(cols) + 1))  # +1 for user_id
        col_str = ", ".join([f"[{c}]" for c in cols])

        query = f"""
            INSERT INTO ExpectationResponse (user_id, {col_str})
            VALUES ({placeholders})
        """
        print("🟢 DEBUG: Final query ->", query)
        print("🟢 DEBUG: Values count ->", len([user_id] + vals))
        print("🟢 DEBUG: Columns ->", cols)

        cur.execute(query, [user_id] + vals)
        conn.commit()

        return jsonify({"message": "Preferences saved successfully"}), 201

    except Exception as e:
        import traceback
        print("🔴 ERROR in save_expectation_response:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            conn.close()
        except:
            pass

@expectations_bp.route('/api/check-expectations/<int:user_id>', methods=['GET'])
def check_expectations(user_id: int):
    """Check if expectations exist for user"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM ExpectationResponse 
            WHERE user_id = ?
        """, (user_id,))
        
        row = cur.fetchone()
        exists = row[0] > 0 if row else False
        
        return jsonify({"exists": exists}), 200
        
    except Exception as e:
        print(f"Error checking expectations: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass