# routes/matching_routes.py
from flask import Blueprint, request, jsonify, current_app
import numpy as np
from sqlalchemy import func
from models import LLMGeneratedQuestions, Marriage, Users, ExpectationResponse, db
from matching_functions import match_expectation_with_profiles, generate_expectation_explanation
from character_functions import cosine_sim, generate_character_llm_explanation, generate_character_fallback_explanation
from database import fetch_expectation_data, fetch_marriage_profile_data
from config import COLOR_KEYS

# matching_bp = Blueprint('matching', __name__)

# @matching_bp.route('/match')
# @matching_bp.route('/match/<int:user_id>')
# def unified_match(user_id=None):

matching_bp = Blueprint('matching', __name__)

@matching_bp.route('/match', methods=['GET'])
@matching_bp.route('/match/<int:user_id>', methods=['GET'])
@matching_bp.route('/api/match', methods=['GET'])
@matching_bp.route('/api/match/<int:user_id>', methods=['GET'])
def unified_match(user_id=None):
    """Unified match endpoint that handles all three modes"""
    # (rest of your function exactly as it is)

    """Unified match endpoint that handles all three modes"""
    # Remove the incorrect db.app.app_context() and use current_app instead
    # The app context is already provided by Flask for route handlers
    
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

    # 🚨 DECISION: Handle all three modes
    if mode == "expectation-only":
        print("🎯 Using PURE EXPECTATION matching")
        # Pure expectation matching only (with mandatory filtering)
        expectation_matches = match_expectation_with_profiles(user_id)
        
        if not expectation_matches:
            return jsonify({"error": f"No matches found for user_id={user_id}"}), 404

        # Convert to frontend format with expectation scores only
        matches_by_range = {
            "90-100": [],
            "80-89": [], 
            "70-79": [],
            "60-69": [],
            "below_60": []
        }
        
        for match in expectation_matches:
            # Use expectation score only (0-1 scale) to percentage (0-100)
            score_percentage = match.get("expectation_score", 0) * 100
            
            # Determine which range this match belongs to
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
            
            # Create match object with expectation score only
            match_obj = {
                "user_id": match["user_id"],
                "name": match["name"],
                "gender": match.get("gender", ""),
                "city": match.get("location", ""),
                "score_expect": match.get("expectation_score", 0),  # Raw score (0-1)
                "score_color": match.get("character_score", 0),     # Still include but not used for sorting
                "final_score": round(score_percentage, 2),          # Percentage for display
                "blue": 0, "green": 0, "yellow": 0, "red": 0,
                "explanations": [],
                "explanation_source": "expectation"
            }
            
            matches_by_range[range_key].append(match_obj)

        # Get user data for input_user
        user = Users.query.filter_by(user_id=user_id).first()
        
        input_user = {
            "user_id": user_id,
            "role": "marriage",
            "name": user.name if user else "Unknown",
            "blue": 0, "green": 0, "yellow": 0, "red": 0,  # Not used in this mode
            "created_at": None,
        }

        print(f"✅ DEBUG: Returning {len(expectation_matches)} pure expectation matches")
        
        return jsonify({
            "input_user": input_user,
            "matches": matches_by_range,
            "count": len(expectation_matches),
            "mode": "expectation-only"
        })
        
    elif mode == "character":
        print("🎯 Using PURE CHARACTER matching - NO EXPECTATION FILTERING")
        
        # Get current user to know gender
        current_user = Marriage.query.filter_by(user_id=user_id).first()
        if not current_user:
            return jsonify({"error": f"No marriage profile found for user_id={user_id}"}), 404

        user_gender = (current_user.gender or "").lower()
        print(f"🔍 DEBUG: Current user gender: {user_gender}")

        # Opposite gender profiles only - NO MANDATORY FILTERING
        if user_gender.startswith('male'):
            opposite_profiles = Marriage.query.filter(func.lower(func.trim(Marriage.gender)) == "female").all()
        elif user_gender.startswith('female'):
            opposite_profiles = Marriage.query.filter(func.lower(func.trim(Marriage.gender)) == "male").all()
        else:
            opposite_profiles = Marriage.query.filter(Marriage.gender != current_user.gender).all()

        print(f"🔍 DEBUG: Found {len(opposite_profiles)} opposite gender profiles (NO MANDATORY FILTERING)")

        # Get base user's character data
        base_llm = LLMGeneratedQuestions.query.filter_by(user_id=user_id).first()
        if not base_llm:
            return jsonify({"error": f"No character data found for user_id={user_id}"}), 404

        u_vec = base_llm.color_vec()

        # Calculate character scores for ALL opposite gender profiles
        candidates = []
        all_ids = [profile.user_id for profile in opposite_profiles]
        
        # Get LLM data for all candidates
        llm_data = LLMGeneratedQuestions.query.filter(LLMGeneratedQuestions.user_id.in_(all_ids)).all()
        llm_map = {l.user_id: l for l in llm_data}

        for profile in opposite_profiles:
            if profile.user_id in llm_map:
                llm_other = llm_map[profile.user_id]
                v_vec = llm_other.color_vec()
                
                # Compute character similarity
                character_score = cosine_sim(u_vec, v_vec)
                
                # Convert to percentage for display
                score_percentage = round(character_score * 100, 2)
                
                candidates.append({
                    "user_id": profile.user_id,
                    "name": profile.full_name,
                    "gender": profile.gender,
                    "location": profile.current_city,
                    "score_color": character_score,  # Raw score (0-1)
                    "score_expect": 0,  # Not used in this mode
                    "final_score": score_percentage,  # Percentage for display
                    "blue": llm_other.blue,
                    "green": llm_other.green,
                    "yellow": llm_other.yellow,
                    "red": llm_other.red,
                    "explanations": [],
                    "explanation_source": "character"
                })

        # Sort by character score (highest first)
        candidates.sort(key=lambda x: x["score_color"], reverse=True)
        print(f"🔍 DEBUG: Pure character matching found {len(candidates)} candidates")

        # 🚨 ADD: Detailed debug logging for score distribution
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

        # Show first 10 candidates with detailed scores
        print("🔍 DEBUG: Top 10 candidate scores:")
        for i, candidate in enumerate(candidates[:10]):
            print(f"   {i+1}. {candidate['name']}: raw={candidate['score_color']:.3f}, percentage={candidate['final_score']}%")

        # Group by score ranges
        matches_by_range = {
            "90-100": [],
            "80-89": [], 
            "70-79": [],
            "60-69": [],
            "below_60": []
        }
        
        for candidate in candidates:
            score_percentage = candidate["final_score"]
            
            # Determine which range this match belongs to
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

        # 🚨 ADD: Debug logging to verify range assignment
        print("🔍 DEBUG: Range distribution after grouping:")
        for range_key, matches in matches_by_range.items():
            if matches:
                scores = [m["final_score"] for m in matches]
                print(f"   {range_key}: {len(matches)} users, scores: {min(scores):.1f}% - {max(scores):.1f}%")
            else:
                print(f"   {range_key}: 0 users")

        # Get user data for input_user
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
    
    else:  # expectation mode (default - expectation + character refinement)
        print("🎯 Using EXPECTATION + CHARACTER matching")
        # Use expectation-based matching with character refinement
        expectation_matches = match_expectation_with_profiles(user_id)
        
        if not expectation_matches:
            return jsonify({"error": f"No matches found for user_id={user_id}"}), 404

        # Convert to the expected frontend format with combined scores
        matches_by_range = {
            "90-100": [],
            "80-89": [], 
            "70-79": [],
            "60-69": [],
            "below_60": []
        }
        
        for match in expectation_matches:
            # Convert overall_score (0-1 scale) to percentage (0-100)
            score_percentage = match.get("overall_score", 0) * 100
            
            # Determine which range this match belongs to
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
            
            # Create match object with combined scores
            match_obj = {
                "user_id": match["user_id"],
                "name": match["name"],
                "gender": match.get("gender", ""),
                "city": match.get("location", ""),
                "final_score": round(score_percentage, 2),
                "score_expect": match.get("expectation_score", 0),
                "score_color": match.get("character_score", 0),
                "blue": 0, "green": 0, "yellow": 0, "red": 0,
                "explanations": [],
                "explanation_source": "expectation"
            }
            
            matches_by_range[range_key].append(match_obj)

        # Get user data for input_user
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
def get_compatibility_explanation():
    user_id = request.args.get("user_id", type=int)
    target_user_id = request.args.get("target_user_id", type=int)
    mode = request.args.get("mode", "expectation-only")

    if not user_id or not target_user_id:
        return jsonify({"error": "user_id and target_user_id are required"}), 400

    try:
        # TAB 1 → EXPECTATION ONLY (Rule-based)
        if mode == "expectation-only":
            exp_user = fetch_expectation_data(user_id)
            profile_user = fetch_marriage_profile_data(target_user_id)

            explanations = generate_expectation_explanation(exp_user, profile_user)

            return jsonify({
                "mode": "expectation-only",
                "explanations": explanations,
                "source": "expectation-fallback"
            })

        # TAB 2 → CHARACTER ONLY (LLM-ONLY)
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

            print(f"🎯 Generating AI character analysis for users {user_id} and {target_user_id}...")
            character_explanations = generate_character_llm_explanation(u_vec, v_vec)

            return jsonify({
                "mode": "character",
                "explanations": character_explanations,
                "source": "character-llm"
            })

        # TAB 3 → EXPECTATION + CHARACTER (Mixed)
        elif mode == "expectation":
            exp_user = fetch_expectation_data(user_id)
            profile_user = fetch_marriage_profile_data(target_user_id)

            expectation_part = generate_expectation_explanation(exp_user, profile_user)

            llm1 = LLMGeneratedQuestions.query.filter_by(user_id=user_id).first()
            llm2 = LLMGeneratedQuestions.query.filter_by(user_id=target_user_id).first()

            character_explanations = []
            if llm1 and llm2:
                try:
                    u_vec = llm1.color_vec()
                    v_vec = llm2.color_vec()
                    character_explanations = generate_character_llm_explanation(u_vec, v_vec)
                    source_type = "character-llm"
                except Exception as e:
                    print(f"🔴 LLM failed, using backend fallback: {e}")
                    character_explanations = generate_character_fallback_explanation(u_vec, v_vec)
                    source_type = "character-fallback"
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
        return jsonify({
            "explanations": [f"❌ Service temporarily unavailable: {str(e)}"],
            "source": "error"
        }), 500




