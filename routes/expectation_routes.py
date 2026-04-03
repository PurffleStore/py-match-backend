# routes/expectation_routes.py
from flask import Blueprint, request, jsonify
import json

from .auth_routes import get_db_connection
from database import row_to_dict
from config import APP_ENV

expectations_bp = Blueprint('expectations', __name__)


def is_local():
    return APP_ENV == "local"


def sql_param():
    return "?" if is_local() else "%s"


def quote_col(col_name: str) -> str:
    return f"[{col_name}]" if is_local() else f"`{col_name}`"


def row_value(row, key=None, index=None):
    if row is None:
        return None

    if isinstance(row, dict):
        if key is not None:
            return row.get(key)
        if index is not None:
            values = list(row.values())
            return values[index] if index < len(values) else None
        return None

    if index is not None:
        return row[index]

    return None


def row_to_dict_compat(cur, row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return row_to_dict(cur, row)


@expectations_bp.route('/api/existing-preferences/<int:user_id>', methods=['GET'])
def get_existing_preferences(user_id: int):
    """Get existing preferences data for a user"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if is_local():
            query = """
                SELECT TOP 1 * FROM ExpectationResponse
                WHERE user_id = ?
                ORDER BY created_at DESC
            """
        else:
            query = """
                SELECT * FROM ExpectationResponse
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """

        cur.execute(query, (user_id,))
        row = cur.fetchone()

        if row is None:
            return jsonify({"error": "No preferences found"}), 404

        preferences = row_to_dict_compat(cur, row)

        cur.execute("SELECT column_key FROM ExpectationQuestions WHERE input_type = 'multi_select'")
        multi_select_rows = cur.fetchall()
        multi_select_keys = [row_value(r, "column_key", 0) for r in multi_select_rows]

        for key in multi_select_keys:
            if key in preferences and preferences[key]:
                if isinstance(preferences[key], str):
                    preferences[key] = [
                        item.strip()
                        for item in preferences[key].split(",")
                        if item.strip()
                    ]

        return jsonify(preferences), 200

    except Exception as e:
        print(f"Error fetching existing preferences: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


@expectations_bp.route('/api/update-preferences/<int:user_id>', methods=['PUT'])
def update_preferences(user_id: int):
    """Update existing preferences"""
    data = request.get_json(force=True) or {}

    if not user_id:
        return jsonify({"error": "User ID is required."}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        print("🟢 DEBUG UPDATE: Incoming data keys ->", list(data.keys()))

        mandatory_fields = data.get('_mandatory_fields', {})
        print("🎯 DEBUG UPDATE: Mandatory fields received:", mandatory_fields)

        set_parts = []
        values = []
        param = sql_param()

        if '_mandatory_fields' in data:
            set_parts.append(f"{quote_col('_mandatory_fields')} = {param}")
            if isinstance(mandatory_fields, dict):
                mandatory_json = json.dumps(mandatory_fields, ensure_ascii=False)
            else:
                mandatory_json = str(mandatory_fields)
            values.append(mandatory_json)
            print("✅ DEBUG UPDATE: Adding _mandatory_fields to update:", mandatory_json)

        field_mapping = {
            'pref_live_with_inlaws': 'live_with_inlaws',
            'accept_financial_support_to_parents': 'financial_support_to_parents'
        }

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

        cur.execute("SELECT column_key, input_type FROM ExpectationQuestions")
        field_type_rows = cur.fetchall()
        field_types = {
            row_value(r, "column_key", 0): row_value(r, "input_type", 1)
            for r in field_type_rows
        }

        for key in valid_fields:
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
                        set_parts.append(f"{quote_col(db_field_name)} = {param}")
                        values.append(final_value)
                    else:
                        set_parts.append(f"{quote_col(db_field_name)} = {param}")
                        values.append("")

                elif field_type == 'multi_select' and isinstance(value, str):
                    clean_value = value.strip()
                    clean_value = clean_value.replace('[', '').replace(']', '').replace('"', '').strip()
                    if clean_value.startswith(',') or clean_value.endswith(','):
                        clean_value = clean_value.strip(',')

                    print(f"🟢 Cleaning multi_select string: '{clean_value}'")
                    set_parts.append(f"{quote_col(db_field_name)} = {param}")
                    values.append(clean_value)

                elif value is not None:
                    final_value = str(value).strip() if isinstance(value, str) else value
                    print(f"🟢 Storing single value: '{final_value}'")
                    set_parts.append(f"{quote_col(db_field_name)} = {param}")
                    values.append(final_value)

                else:
                    set_parts.append(f"{quote_col(db_field_name)} = {param}")
                    values.append("")

        if not set_parts:
            return jsonify({"error": "No valid fields to update"}), 400

        values.append(user_id)
        set_clause = ", ".join(set_parts)
        query = f"UPDATE ExpectationResponse SET {set_clause} WHERE user_id = {param}"

        print(f"🟢 DEBUG UPDATE: Executing query: {query}")
        print(f"🟢 DEBUG UPDATE: Values: {values}")

        cur.execute(query, values)
        conn.commit()

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
            if conn:
                conn.close()
        except:
            pass


@expectations_bp.route('/api/check-mandatory-fields/<int:user_id>', methods=['GET'])
def check_mandatory_fields(user_id: int):
    """Check current mandatory fields in database"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        param = sql_param()

        cur.execute(f"""
            SELECT user_id, _mandatory_fields
            FROM ExpectationResponse
            WHERE user_id = {param}
        """, (user_id,))

        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "No preferences found for user"}), 404

        user_id_val = row_value(row, "user_id", 0)
        mandatory_val = row_value(row, "_mandatory_fields", 1)

        result = {
            "user_id": user_id_val,
            "_mandatory_fields": mandatory_val,
            "_mandatory_fields_type": str(type(mandatory_val)),
            "exists_in_db": mandatory_val is not None
        }

        print("🔍 CHECK MANDATORY FIELDS:", result)

        return jsonify(result), 200

    except Exception as e:
        print(f"Error checking mandatory fields: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


@expectations_bp.route('/api/expectation-questions', methods=['GET'])
def get_expectation_questions():
    conn = None
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
                "id": row_value(r, "id", 0),
                "question": row_value(r, "question", 1),
                "options": (
                    row_value(r, "options", 2).split(",")
                    if row_value(r, "options", 2) else []
                ),
                "input_type": row_value(r, "input_type", 3),
                "column_key": row_value(r, "column_key", 4),
                "category": row_value(r, "category", 5)
            })
        return jsonify(out), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


@expectations_bp.route('/api/expectation-response', methods=['POST'])
def save_expectation_response():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        param = sql_param()

        cur.execute("SELECT column_key, input_type FROM ExpectationQuestions")
        field_rows = cur.fetchall()
        valid_fields = {
            row_value(r, "column_key", 0): row_value(r, "input_type", 1)
            for r in field_rows
        }

        expectation_model_fields = [
            'pref_age_range', 'pref_height_range', 'pref_current_city', 'pref_countries',
            'pref_languages', 'health_constraints', 'pref_diet', 'accept_smoking',
            'accept_alcohol', 'pref_fitness', 'pref_family_type', 'live_with_inlaws',
            'children_timeline', 'open_to_adoption', 'pref_conflict_approach',
            'pref_financial_style', 'religion_alignment', 'pref_shared_hobbies',
            'travel_pref', 'pet_pref', 'pref_income_range', 'deal_breakers',
            'other_non_negotiables', 'pref_education_level', 'pref_employment_status',
            'expectation_summary', '_mandatory_fields', 'skin_tone', 'marital_status',
            'daily_routine', 'family_communication_frequency', 'relaxation_mode',
            'pref_partner_relocation', 'financial_support_to_parents',
            'pref_career_aspirations', 'pref_live_with_parents'
        ]

        for field in expectation_model_fields:
            if field not in valid_fields:
                valid_fields[field] = 'text'

        print("🟢 DEBUG: Valid fields ->", list(valid_fields.keys()))
        print("🟢 DEBUG: Incoming data keys ->", list(data.keys()))

        cols, vals = [], []

        mandatory_fields = data.get('_mandatory_fields', {})
        if '_mandatory_fields' in data:
            cols.append('_mandatory_fields')
            if isinstance(mandatory_fields, dict):
                mandatory_json = json.dumps(mandatory_fields, ensure_ascii=False)
                vals.append(mandatory_json)
            else:
                vals.append(str(mandatory_fields))
            print("✅ DEBUG: Added _mandatory_fields:", mandatory_fields)

        for key, field_type in valid_fields.items():
            if key in data and key != 'user_id' and key != '_mandatory_fields':
                value = data[key]
                print(f"🟡 Processing field {key} (type: {field_type}): {value}")

                if value is None or value == '':
                    continue

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
                        cols.append(key)
                        vals.append(final_value)
                    else:
                        continue

                elif field_type == 'multi_select' and isinstance(value, str):
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
                    final_value = str(value).strip() if isinstance(value, str) else value
                    if final_value:
                        print(f"🟢 Storing single value: '{final_value}'")
                        cols.append(key)
                        vals.append(final_value)

        if not cols:
            return jsonify({"error": "No valid fields found in request"}), 400

        placeholders = ", ".join([param] * (len(cols) + 1))
        col_str = ", ".join([quote_col(c) for c in cols])

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
            if conn:
                conn.close()
        except:
            pass


@expectations_bp.route('/api/check-expectations/<int:user_id>', methods=['GET'])
def check_expectations(user_id: int):
    """Check if expectations exist for user"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        param = sql_param()

        cur.execute(f"""
            SELECT COUNT(*) as count
            FROM ExpectationResponse
            WHERE user_id = {param}
        """, (user_id,))

        row = cur.fetchone()

        if isinstance(row, dict):
            count = row.get("count", 0)
        else:
            count = row[0] if row else 0

        exists = count > 0
        return jsonify({"exists": exists}), 200

    except Exception as e:
        print(f"Error checking expectations: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass