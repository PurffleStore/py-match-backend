# matching_functions.py
import json
import random
import pandas as pd
import numpy as np
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func
from models import ExpectationResponse, Marriage, LLMGeneratedQuestions, Users, db
from character_functions import calculate_character_similarity


def values_match(expect_value, profile_value, field_name):
    """Check if expectation value matches profile value with special handling for all fields"""
    # Handle None values before using pd.isna
    if expect_value is None or (hasattr(expect_value, 'isna') and pd.isna(expect_value)) or expect_value in ['', 'No preference', 'Any', 'All']:
        return True  # No preference means match with any value
    
    # Convert to string safely
    expect_str = str(expect_value).lower().strip() if expect_value is not None else ""
    profile_str = str(profile_value).lower().strip() if profile_value is not None else ""
    
    # Handle empty profile values
    if profile_value is None or (hasattr(profile_value, 'isna') and pd.isna(profile_value)) or profile_str in ['', 'none', 'null']:
        return False
    
    # 🚨 FIELD-SPECIFIC MATCHING LOGIC
        
    if field_name == 'pref_age_range':
        try:
            if '-' in expect_str and profile_value:
                min_age, max_age = map(int, expect_str.split('-'))
                from datetime import date, datetime

                # 🧠 Handle both string and datetime.date types
                if isinstance(profile_value, date):
                    birth_date = profile_value
                elif isinstance(profile_value, str):
                    # Try common formats
                    try:
                        birth_date = datetime.strptime(profile_value, "%Y-%m-%d").date()
                    except ValueError:
                        birth_date = datetime.strptime(profile_value, "%d-%m-%Y").date()
                else:
                    print(f"⚠️ Unsupported date type: {type(profile_value)}")
                    return False

                # ✅ Calculate age accurately
                today = date.today()
                age = today.year - birth_date.year - (
                    (today.month, today.day) < (birth_date.month, birth_date.day)
                )

                # ✅ Inclusive range with ±1 tolerance
                if (min_age - 1) <= age <= (max_age + 1):
                    return True
                else:
                    return False
            return True
        except Exception as e:
            print(f"⚠️ Age parsing error: {e} for {profile_value}")
            return False

    elif field_name == 'pref_height_range':
        try:
            cleaned = expect_str.replace('cm', '').replace(' ', '').lower()
            profile_height = int(profile_str.replace('cm', '').replace(' ', ''))

            # 190+
            if cleaned.endswith('+'):
                base = int(cleaned.replace('+', ''))
                return profile_height >= base

            # 181-189
            if '-' in cleaned:
                min_h, max_h = map(int, cleaned.split('-'))
                return min_h <= profile_height <= max_h

            # Single value
            return profile_height == int(cleaned)

        except:
            return False
    
    # 3. City matching (pref_current_city vs current_city)
    elif field_name == 'pref_current_city':
        pref_cities = [city.strip().lower() for city in expect_str.split(',')]
        return profile_str in pref_cities
    
    # 4. Country matching (pref_countries vs country)
    elif field_name == 'pref_countries':
        try:
            # Handle None/empty values
            if not expect_str or not profile_str:
                return False
                
            # Normalise expectation values
            pref_countries = [c.strip().lower() for c in str(expect_str).split(',') if c.strip()]
            
            # If user selected No Preference → auto match
            if 'no preference' in pref_countries:
                return True
            
            # Normalise profile value
            profile_country = str(profile_str).lower().strip()
            
            return profile_country in pref_countries
            
        except Exception as e:
            print(f"Error in country matching: {e}")
            return False
    
    # 5. Languages matching (pref_languages vs languages_spoken)
    elif field_name == 'pref_languages':
        pref_langs = [lang.strip().lower() for lang in expect_str.split(',')]
        profile_langs = [lang.strip().lower() for lang in profile_str.split(',')]
        return any(lang in profile_langs for lang in pref_langs)
    
    # 6. Health Constraints matching
    elif field_name == 'health_constraints':
        health_mapping = {
            'healthy': ['none', 'healthy'],
            'minor': ['minor'],
            'chronic': ['chronic'],
            'allergies': ['allergies']
        }
        for exp_health, profile_options in health_mapping.items():
            if expect_str == exp_health:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 7. Diet matching - STRICT EXACT MATCHING
    elif field_name == 'pref_diet':
        diet_options = {
            'vegetarian': ['vegetarian'],
            'non-vegetarian': ['non-vegetarian'],
            'eggetarian': ['eggetarian']
        }
        
        expect_clean = expect_str.replace('-', '').replace(' ', '')
        profile_clean = profile_str.replace('-', '').replace(' ', '')
        
        if expect_clean == profile_clean:
            return True
        
        for diet_type, variations in diet_options.items():
            expect_variations = [v.replace('-', '').replace(' ', '') for v in variations]
            profile_variations = [v.replace('-', '').replace(' ', '') for v in variations]
            
            if expect_clean in expect_variations:
                return profile_clean in profile_variations
        
        return False
    
    # 8. Smoking matching
    elif field_name == 'accept_smoking':
        smoking_mapping = {
            'never': ['no'],
            'no preference': ['yes', 'no', 'occasionally'],
            'occasionally': ['occasionally', 'yes']
        }
        for exp_option, profile_options in smoking_mapping.items():
            if expect_str == exp_option:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 9. Alcohol matching
    elif field_name == 'accept_alcohol':
        alcohol_mapping = {
            'never': ['no'],
            'no preference': ['yes', 'no', 'occasionally'],
            'occasionally': ['occasionally', 'yes']
        }
        for exp_option, profile_options in alcohol_mapping.items():
            if expect_str == exp_option:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 10. Fitness matching
    elif field_name == 'pref_fitness':
        fitness_mapping = {
            'low': ['low'],
            'moderate': ['moderate'],
            'high': ['high'],
            'no preference': ['low', 'moderate', 'high']
        }
        for exp_level, profile_options in fitness_mapping.items():
            if expect_str == exp_level:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 11. Family Type matching
    elif field_name == 'pref_family_type':
        family_mapping = {
            'nuclear': ['nuclear'],
            'joint': ['joint'],
            'extended': ['extended'],
            'no preference': ['nuclear', 'joint', 'extended']
        }
        for exp_type, profile_options in family_mapping.items():
            if expect_str == exp_type:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 12. Live with In-laws matching
    elif field_name == 'live_with_inlaws':
        inlaw_mapping = {
            'yes': ['yes'],
            'no': ['no'],
            'maybe': ['maybe'],
            'no preference': ['yes', 'no', 'maybe']
        }
        for exp_option, profile_options in inlaw_mapping.items():
            if expect_str == exp_option:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 13. Children Timeline matching
    elif field_name == 'children_timeline':
        timeline_mapping = {
            'within 1 year': ['within 1 year'],
            '1-3 years': ['1-3 years'],
            'after 3 years': ['after 3 years'],
            'not planning': ['not planning', 'no preference'],
            'no preference': ['within 1 year', '1-3 years', 'after 3 years', 'not planning', 'no preference']
        }
        for exp_timeline, profile_options in timeline_mapping.items():
            if expect_str == exp_timeline:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 14. Open to Adoption matching
    elif field_name == 'open_to_adoption':
        adoption_mapping = {
            'yes': ['yes'],
            'no': ['no'],
            'maybe': ['maybe'],
            'no preference': ['yes', 'no', 'maybe']
        }
        for exp_option, profile_options in adoption_mapping.items():
            if expect_str == exp_option:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 15. Conflict Approach matching
    elif field_name == 'pref_conflict_approach':
        conflict_mapping = {
            'discuss calmly': ['discuss calmly'],
            'problem-solving': ['problem-solving'],
            'compromise': ['compromise'],
            'avoid': ['avoid'],
            'decide fast': ['decide fast'],
            'no preference': ['discuss calmly', 'problem-solving', 'compromise', 'avoid', 'decide fast']
        }
        for exp_approach, profile_options in conflict_mapping.items():
            if expect_str == exp_approach:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 16. Financial Style matching
    elif field_name == 'pref_financial_style':
        financial_mapping = {
            'budget-oriented': ['budget-oriented'],
            'spend-oriented': ['spend-oriented'],
            'balanced': ['balanced'],
            'no preference': ['budget-oriented', 'spend-oriented', 'balanced']
        }
        for exp_style, profile_options in financial_mapping.items():
            if expect_str == exp_style:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 17. Religion matching - Comprehensive version
    elif field_name in ['pref_religion', 'religion_alignment', 'religion']:
        # Handle "No preference" case
        if expect_str in ['no preference', 'any', 'all']:
            return True
        
        # Split expected religions (comma-separated)
        expected_religions = [religion.strip().lower() for religion in expect_str.split(',')]
        profile_religion = profile_str.lower().strip()
        
        # Handle cases where profile has multiple religions too
        profile_religions = [religion.strip().lower() for religion in profile_str.split(',')]
        
        # Check if any profile religion matches any expected religion
        return any(religion in expected_religions for religion in profile_religions)
    
    # 18. Income Range matching
    elif field_name == 'pref_income_range':
        if expect_str.lower() == 'prefer not to say' or profile_str.lower() == 'prefer not to say':
            return True
        if '-' in expect_str and '-' in profile_str:
            try:
                exp_min, exp_max = map(lambda x: int(x.replace('₹', '').replace(',', '').strip()), expect_str.split('-'))
                prof_min, prof_max = map(lambda x: int(x.replace('₹', '').replace(',', '').strip()), profile_str.split('-'))
                # Check if ranges overlap
                return not (prof_max < exp_min or prof_min > exp_max)
            except (ValueError, AttributeError):
                pass
        return True
    
    # 19. Education Level matching
    elif field_name == 'pref_education_level':
        education_mapping = {
            'doctorate': ['doctorate', 'phd'],
            'master': ['master', 'masters', 'postgraduate'],
            'bachelor': ['bachelor', 'bachelors', 'undergraduate'],
            'diploma': ['diploma', 'certificate'],
            'school': ['school', 'secondary', 'higher secondary'],
            'no preference': ['doctorate', 'master', 'bachelor', 'diploma', 'school']
        }
        for exp_level, profile_options in education_mapping.items():
            if expect_str == exp_level:
                return any(option in profile_str for option in profile_options)
        return any(option in profile_str for option in education_mapping.get(expect_str, [expect_str]))
    
    # 20. Employment Status matching
    elif field_name == 'pref_employment_status':
        employment_mapping = {
            'employed': ['Employed'],
            'self-employed': ['Self-employed'],
            'unemployed': ['Unemployed'], 
            'freelancer': ['Freelancer'],
            'government employee': ['Government employee'],
            'no preference': ['Employed', 'Self-employed', 'Unemployed', 'Freelancer', 'Government employee']
        }
        
        # Handle "no preference" case
        if expect_str == 'no preference':
            return True
            
        # Get expected options
        expected_options = employment_mapping.get(expect_str, [expect_str])
        
        # Exact match comparison (case-insensitive)
        profile_clean = profile_str.strip().lower()
        return any(profile_clean == option.lower() for option in expected_options)
    
    # 21. Travel Preference matching
    elif field_name == 'travel_pref':
        travel_mapping = {
            'frequent traveler': ['frequent traveler'],
            'occasional traveler': ['occasional traveler'],
            'homebody': ['homebody'],
            'no preference': ['frequent traveler', 'occasional traveler', 'homebody']
        }
        for exp_travel, profile_options in travel_mapping.items():
            if expect_str == exp_travel:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 22. Pet Preference matching
    elif field_name == 'pet_pref':
        pet_mapping = {
            'open to pets': ['yes'],
            'must like pets': ['yes'],
            'no pets': ['no'],
            'no preference': ['yes', 'no']
        }
        for exp_pet, profile_options in pet_mapping.items():
            if expect_str == exp_pet:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 23. Deal Breakers - Complex logic (check if profile has any deal breakers)
    elif field_name == 'deal_breakers':
        if pd.isna(expect_value) or expect_str in ['', 'none']:
            return True
        
        # What profiles actually track
        PROFILE_DEAL_BREAKERS = {'smoking', 'different religion', 'alcohol', 
                                'financial irresponsibility', 'no desire for children'}
        
        expect_breakers = {breaker.strip().lower() for breaker in expect_str.split(',')}
        
        # If expectation includes untrackable deal breakers → NO MATCH
        if not expect_breakers.issubset(PROFILE_DEAL_BREAKERS):
            return False
        
        # Check against actual profile data
        if pd.isna(profile_value) or not str(profile_value).strip():
            profile_breakers = set()
        else:
            profile_breakers = {breaker.strip().lower() for breaker in str(profile_value).split(',')}
        
        # No match if profile has any of the expected deal breakers
        return len(expect_breakers.intersection(profile_breakers)) == 0
    
    # 24. Daily Routine matching
    elif field_name == 'daily_routine':
        routine_mapping = {
            'early riser': ['early riser'],
            'night owl': ['night owl'],
            'balanced': ['balanced'],
            'no preference': ['early riser', 'night owl', 'balanced']
        }
        for exp_routine, profile_options in routine_mapping.items():
            if expect_str == exp_routine:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 25. Family Communication Frequency matching
    elif field_name == 'family_communication_frequency':
        comm_mapping = {
            'daily': ['daily'],
            'weekly': ['weekly'],
            'monthly': ['monthly'],
            'occasionally': ['occasionally'],
            'no preference': ['daily', 'weekly', 'monthly', 'occasionally']
        }
        for exp_freq, profile_options in comm_mapping.items():
            if expect_str == exp_freq:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 26. pref_shared_hobbies
    elif field_name == "pref_shared_hobbies":
        # Expectation list (split by comma)
        expect_list = [x.strip().lower() for x in expect_str.split(",") if x.strip()]

        # Profile list
        profile_list = [x.strip().lower() for x in profile_str.split(",") if x.strip()]

        # ANY overlap → MATCH
        return any(h in profile_list for h in expect_list)
    
    # 27. pref_partner_relocation 
    elif field_name == 'pref_partner_relocation':
        relocation_mapping = {
            'yes': ['yes'],
            'no': ['no'],
            'maybe': ['maybe'],
            'no preference': ['yes', 'no', 'maybe']
        }
        for exp_option, profile_options in relocation_mapping.items():
            if expect_str == exp_option:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 28. pref_live_with_parents 
    elif field_name == 'pref_live_with_parents':
        live_mapping = {
            'yes': ['yes'],
            'no': ['no'],
            'maybe': ['maybe'],
            'no preference': ['yes', 'no', 'maybe']
        }
        for exp_option, profile_options in live_mapping.items():
            if expect_str == exp_option:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 29. financial_support_to_parents 
    elif field_name == 'financial_support_to_parents':
        support_mapping = {
            'yes': ['yes'],
            'no': ['no'],
            'no preference': ['yes', 'no']
        }
        for exp_option, profile_options in support_mapping.items():
            if expect_str == exp_option:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 30. other_non_negotiables 
    elif field_name == 'other_non_negotiables':
        expect_list = [x.strip().lower() for x in expect_str.split(',') if x.strip()]
        profile_list = [x.strip().lower() for x in profile_str.split(',') if x.strip()]

        # Match if ANY expected non-negotiable is found in profile
        return any(item in profile_list for item in expect_list)
    
    # 31. skin_tone 
    elif field_name == 'skin_tone':
        tone_mapping = {
            'fair': ['fair'],
            'medium': ['medium'],
            'dark': ['dark'],
            'no preference': ['fair', 'medium', 'dark']
        }
        for exp_tone, profile_options in tone_mapping.items():
            if expect_str == exp_tone:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 32. marital_status 
    elif field_name == 'marital_status':
        status_mapping = {
            'single': ['single'],
            'divorced': ['divorced'],
            'widowed': ['widowed'],
            'no preference': ['single', 'divorced', 'widowed']
        }
        for exp_status, profile_options in status_mapping.items():
            if expect_str == exp_status:
                return profile_str in profile_options
        return expect_str == profile_str
    
    # 33. relaxation_mode 
    elif field_name == 'relaxation_mode':
        # No preference → always match
        if expect_str in ['no preference', 'any']:
            return True

        expect_list = [x.strip().lower() for x in expect_str.split(',') if x.strip()]
        profile_list = [x.strip().lower() for x in profile_str.split(',') if x.strip()]

        # Any overlap = match
        return any(item in profile_list for item in expect_list)
    
    elif field_name == 'expectation_summary':
        if not expect_value or str(expect_value).strip().lower() in ['', 'no preference', 'any']:
            return True
        
        if not profile_value or str(profile_value).strip().lower() in ['', 'none', 'null']:
            return False
        
        return compare_expectation_with_remark(
            str(expect_value).strip(), 
            str(profile_value).strip()
        )
    
    # 34. Career Aspirations matching
    elif field_name == 'pref_career_aspirations':
        career_mapping = {
            'entrepreneurship': ['entrepreneurship', 'entrepreneur'],
            'leadership': ['leadership'],
            'stable job': ['stable job'],
            'work-life balance': ['work-life balance'],
            'research': ['research'],
            'creativity': ['creativity'],
            'social impact': ['social impact'],
            'no preference': ['entrepreneurship', 'leadership', 'stable job', 'work-life balance', 'research', 'creativity', 'social impact']
        }
        for exp_career, profile_options in career_mapping.items():
            if expect_str == exp_career:
                return any(option in profile_str for option in profile_options)
        return any(option in profile_str for option in career_mapping.get(expect_str, [expect_str]))
    
    # Default: Exact match for other fields
    else:
        return expect_str == profile_str

def extract_key_concepts(text):
    """Extract key concepts from text using NLP techniques"""
    text = text.lower()
    
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
                  'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been'}
    
    # Concept mapping - words that mean similar things
    concept_groups = {
        'family': ['family', 'parents', 'children', 'siblings', 'home', 'domestic'],
        'career': ['career', 'job', 'work', 'profession', 'business', 'entrepreneur'],
        'balance': ['balance', 'equilibrium', 'harmony', 'work-life'],
        'growth': ['growth', 'development', 'improvement', 'learning', 'progress'],
        'values': ['values', 'principles', 'ethics', 'morals', 'beliefs'],
        'communication': ['communication', 'talking', 'discussing', 'expressing'],
        'shared': ['shared', 'together', 'mutual', 'common', 'joint'],
        'happiness': ['happiness', 'joy', 'fulfillment', 'contentment'],
        'respect': ['respect', 'esteem', 'admiration', 'honor'],
        'understanding': ['understanding', 'comprehension', 'insight', 'empathy'],
        'goals': ['goals', 'objectives', 'aims', 'aspirations', 'ambitions'],
        'compatibility': ['compatibility', 'harmony', 'agreement', 'fit'],
        'lifestyle': ['lifestyle', 'way of life', 'routine', 'daily life'],
        'culture': ['culture', 'cultural', 'tradition', 'heritage'],
        'religion': ['religion', 'faith', 'spiritual', 'belief'],
        'partner': ['partner', 'spouse', 'companion', 'mate'],
        'love': ['love', 'affection', 'care', 'fondness'],
        'trust': ['trust', 'confidence', 'reliance', 'faith'],
        'support': ['support', 'encouragement', 'backing', 'assistance'],
        'stability': ['stability', 'security', 'steadiness', 'reliability']
    }
    
    concepts = set()
    words = text.split()
    
    for word in words:
        word_clean = ''.join(c for c in word if c.isalnum())  # Remove punctuation
        
        if word_clean in stop_words or len(word_clean) < 3:
            continue
            
        # Check if word belongs to any concept group
        for concept, related_words in concept_groups.items():
            if word_clean in related_words:
                concepts.add(concept)
                break
        else:
            # Add the word itself if it's meaningful
            if len(word_clean) > 4:  # Longer words are usually more meaningful
                concepts.add(word_clean)
    
    return concepts

def compare_expectation_with_remark(exp_summary, profile_remark):
    """Compare expectation summary with profile remark using multiple strategies"""
    
    exp_summary_lower = exp_summary.lower()
    profile_remark_lower = profile_remark.lower()
    
    print(f"🔍 Comparing expectation with remark:")
    print(f"   Expectation: '{exp_summary}'")
    print(f"   Remark (first 100 chars): '{profile_remark[:100]}...'")
    
    # Strategy 1: Check for exact phrase matching (for very specific expectations)
    if len(exp_summary.split()) <= 6:  # Short expectations (6 words or less)
        if exp_summary_lower in profile_remark_lower:
            print(f"   ✅ Exact phrase found in remark")
            return True
    
    # Strategy 2: Extract and compare key concepts
    exp_concepts = extract_key_concepts(exp_summary)
    remark_concepts = extract_key_concepts(profile_remark)
    
    print(f"   Expectation concepts: {exp_concepts}")
    print(f"   Remark concepts found: {len(remark_concepts)} total")
    
    # Count overlapping concepts
    overlapping = exp_concepts.intersection(remark_concepts)
    if exp_concepts:
        concept_overlap = len(overlapping) / len(exp_concepts)
    else:
        concept_overlap = 0
    
    print(f"   Concept overlap: {len(overlapping)}/{len(exp_concepts)} = {concept_overlap:.2f}")
    
    # Strategy 3: Use difflib for text similarity (fallback)
    from difflib import SequenceMatcher
    text_similarity = SequenceMatcher(None, exp_summary, profile_remark).ratio()
    print(f"   Text similarity: {text_similarity:.2f}")
    
    # Strategy 4: Check for important keywords
    important_keywords = ['family', 'career', 'balance', 'growth', 'values', 
                         'communication', 'shared', 'respect', 'understanding',
                         'partner', 'love', 'trust', 'support', 'happiness']
    
    keyword_matches = 0
    for keyword in important_keywords:
        if keyword in exp_summary_lower and keyword in profile_remark_lower:
            keyword_matches += 1
    
    print(f"   Important keyword matches: {keyword_matches}")
    
    # Combined decision logic
    # Match if ANY of these conditions are met:
    # 1. Good concept overlap (> 40%)
    # 2. Reasonable text similarity (> 25%)
    # 3. At least 2 important keyword matches
    # 4. Exact phrase match (already handled above)
    
    result = (concept_overlap > 0.4) or (text_similarity > 0.25) or (keyword_matches >= 2)
    
    print(f"   Final decision: {'✅ MATCH' if result else '❌ NO MATCH'}")
    print(f"   Reasons: concept_overlap={concept_overlap:.2f}, "
          f"text_similarity={text_similarity:.2f}, "
          f"keyword_matches={keyword_matches}")
    
    return result

def compute_expectation_score(expect, profile, mandatory_fields):
    """Compute expectation match percentage based on satisfied fields"""
    satisfied_fields = 0
    total_fields_checked = 0
    mandatory_violations = 0

    print(f"🔍 COMPUTE_SCORE: Evaluating profile {profile.user_id} ({profile.full_name}) from {profile.current_city}")

    # 🚨 UPDATED FIELD MAPPING - all expectation fields
    field_mapping = {
        'pref_age_range': 'date_of_birth',
        'pref_height_range': 'height',
        'pref_education_level': 'education_level',
        'pref_employment_status': 'employment_status',
        'expectation_summary': 'remark',  # Map expectation_summary to profile remark
        
        
        'pref_current_city': 'current_city',
        'pref_countries': 'country',
        'pref_diet': 'food_preference',
        'pref_fitness': 'fitness_level',
        'pref_family_type': 'family_type',

        'accept_smoking': 'smoking_habit',
        'accept_alcohol': 'alcohol_habit',
        'pref_languages': 'languages_spoken',
        'religion_alignment': 'religion',
        'pref_partner_relocation': 'relocation_willingness',

        'pref_conflict_approach': 'conflict_approach',
        'pref_financial_style': 'financial_style',
        'pref_shared_hobbies': 'hobbies_interests',
        'travel_pref': 'travel_preference',
        'pet_pref': 'own_pets',
        
        'pref_income_range': 'income_range',
        'live_with_inlaws': 'live_with_inlaws',
        'pref_live_with_parents': 'live_with_parents',
        'financial_support_to_parents': 'support_parents_financially',
        'pref_career_aspirations': 'career_aspirations',

        'children_timeline': 'children_timeline',
        'open_to_adoption': 'open_to_adoption',
        'deal_breakers': 'deal_breakers',
        'other_non_negotiables': 'other_non_negotiables',
        'health_constraints': 'health_constraints',

        'skin_tone': 'skin_tone',
        'marital_status': 'marital_status',
        'daily_routine': 'daily_routine',
        'family_communication_frequency': 'family_communication_frequency',
        'relaxation_mode': 'relaxation_mode'
    }

    # 🚨 DEBUG: Track all field processing
    field_details = []

    # 🚨 CRITICAL FIX: Check ALL mandatory fields FIRST
    print(f"🎯 COMPUTE_SCORE: CHECKING ALL MANDATORY FIELDS: {mandatory_fields}")
    
    for field_name, is_mandatory in mandatory_fields.items():
        if is_mandatory:
            print(f"🎯 COMPUTE_SCORE: Checking mandatory field: {field_name}")
            
            # Get expectation value
            expect_value = getattr(expect, field_name, None)
            
            # Map expectation field to actual profile field
            profile_field_name = field_mapping.get(field_name, field_name)
            profile_value = getattr(profile, profile_field_name, None)
            
            # Special handling for location field
            if field_name == 'pref_current_city' and not profile_value:
                profile_value = profile.current_city
            
            print(f"   Expect: '{expect_value}', Profile: '{profile_value}' (mapped to: {profile_field_name})")

            print(
                f"[COMPARE] Expectation Field: {field_name} "
                f"({expect_value})  ↔  Profile Field: {profile_field_name} "
                f"({profile_value})"
            )

            # If expectation has a value for this mandatory field
            if expect_value and str(expect_value).strip():
                total_fields_checked += 1
                # Profile must have a matching value
                if not profile_value or not str(profile_value).strip():
                    print(f"❌ COMPUTE_SCORE: Mandatory violation: {field_name} - Profile missing value")
                    mandatory_violations += 1
                    field_details.append(f"🚫 MANDATORY FAIL: {field_name}: {expect_value} -> MISSING")
                elif not values_match(expect_value, profile_value, field_name):
                    print(f"❌ COMPUTE_SCORE: Mandatory violation: {field_name} - Values don't match")
                    print(f"   Expect: '{expect_value}', Profile: '{profile_value}'")
                    mandatory_violations += 1
                    field_details.append(f"🚫 MANDATORY FAIL: {field_name}: {expect_value} -> {profile_value}")
                else:
                    satisfied_fields += 1
                    print(f"✅ COMPUTE_SCORE: Mandatory match: {field_name} - '{expect_value}'")
                    field_details.append(f"✅ MANDATORY: {field_name}: {expect_value} -> {profile_value}")
            else:
                print(f"ℹ️ COMPUTE_SCORE: Mandatory field {field_name} has no expectation value, skipping")
                field_details.append(f"➖ MANDATORY NO PREF: {field_name}")

    # 🚨 CRITICAL FIX: REJECT if ANY mandatory violations
    if mandatory_violations > 0:
        print(f"🚫 COMPUTE_SCORE: Profile {profile.user_id} REJECTED due to {mandatory_violations} mandatory violations")
        return 0  # Return 0 score to indicate rejection

    print(f"✅ COMPUTE_SCORE: Profile {profile.user_id} passed ALL mandatory checks")

    # 🚨 NOW CHECK ALL EXPECTATION FIELDS for percentage calculation
    all_expectation_fields = [
        'pref_age_range', 'pref_height_range', 'pref_education_level', 'pref_employment_status',
        'pref_current_city', 'pref_countries', 'pref_diet', 'pref_fitness', 'pref_family_type',
        'accept_smoking', 'accept_alcohol', 'pref_languages', 'religion_alignment',
        'pref_partner_relocation', 'pref_conflict_approach', 'pref_financial_style',
        'pref_shared_hobbies', 'travel_pref', 'pet_pref', 'pref_income_range',
        'live_with_inlaws', 'pref_live_with_parents', 'financial_support_to_parents',
        'pref_career_aspirations', 'children_timeline', 'open_to_adoption',
        'deal_breakers', 'other_non_negotiables', 'health_constraints', 'skin_tone',
        'marital_status', 'daily_routine', 'family_communication_frequency', 'relaxation_mode'
    ]

    # Check ALL expectation fields (both mandatory and optional)
    for field_name in all_expectation_fields:
        # Skip if already processed as mandatory
        if field_name in mandatory_fields and mandatory_fields[field_name]:
            continue
            
        # Map expectation field to profile field
        profile_field_name = field_mapping.get(field_name, field_name)
        expect_value = getattr(expect, field_name, None)
        profile_value = getattr(profile, profile_field_name, None)
        
        # Special handling for location field
        if field_name == 'pref_current_city' and not profile_value:
            profile_value = profile.current_city
        
        # Only count if expectation has a value
        if expect_value and str(expect_value).strip():
            total_fields_checked += 1
            # --- Console Log ---
            print(
                f"[COMPARE] Expectation -> {field_name}: '{expect_value}' "
                f" | Profile -> {profile_field_name}: '{profile_value}'"
            )

            if profile_value and str(profile_value).strip():
                if values_match(expect_value, profile_value, field_name):
                    satisfied_fields += 1
                    print(f"✅ COMPUTE_SCORE: Field match: {field_name}")
                    field_details.append(f"✅ OPTIONAL: {field_name}: {expect_value} -> {profile_value}")
                else:
                    print(f"❌ COMPUTE_SCORE: Field mismatch: {field_name} - Expect: '{expect_value}', Profile: '{profile_value}'")
                    field_details.append(f"❌ OPTIONAL: {field_name}: {expect_value} -> {profile_value}")
            else:
                print(f"❌ COMPUTE_SCORE: Field missing: {field_name} - Profile has no value")
                field_details.append(f"⚠️ OPTIONAL: {field_name}: {expect_value} -> MISSING")
        else:
            field_details.append(f"➖ OPTIONAL NO PREF: {field_name}")

    # 🚨 DEBUG: Print detailed field analysis
    print(f"🔍 COMPUTE_SCORE: Field-by-field analysis:")
    for detail in field_details:
        print(f"   {detail}")
    print(f"🔍 COMPUTE_SCORE: Total fields checked: {total_fields_checked}")
    print(f"🔍 COMPUTE_SCORE: Satisfied fields: {satisfied_fields}")

    # 🚨 Calculate percentage based on satisfied fields vs total fields checked
    if total_fields_checked > 0:
        percentage = (satisfied_fields / total_fields_checked) * 100
        print(f"📊 COMPUTE_SCORE: Field Analysis: {satisfied_fields}/{total_fields_checked} fields satisfied = {percentage:.1f}%")
        
        # Special handling for expectation summary (bonus)
        if hasattr(expect, 'expectation_summary') and expect.expectation_summary and profile.remark:
            from difflib import SequenceMatcher
            exp_summary = str(expect.expectation_summary).lower()
            profile_remark = str(profile.remark).lower()
            
            sim = SequenceMatcher(None, exp_summary, profile_remark).ratio()
            if sim > 0.3:
                # Add bonus for summary similarity (up to 5%)
                bonus = min(sim * 5, 5)
                percentage = min(100, percentage + bonus)
                print(f"✅ COMPUTE_SCORE: Summary similarity bonus: +{bonus:.1f}% (similarity: {sim:.2f})")
        
        final_percentage = round(percentage, 2)
        print(f"🎯 COMPUTE_SCORE: Final expectation percentage: {final_percentage}%")
        return final_percentage / 100  # Return as decimal for consistency
    
    print(f"⚠️ COMPUTE_SCORE: No expectation fields to check for profile {profile.user_id}")
    return 0

def match_expectation_with_profiles(user_id):
    expectation = ExpectationResponse.query.filter_by(user_id=user_id).first()
    if not expectation:
        print(f"❌ No expectation data found for user {user_id}")
        return []

    # 🚨 CRITICAL FIX: Properly parse mandatory fields from database
    mandatory_fields = {}
    if hasattr(expectation, '_mandatory_fields') and expectation._mandatory_fields:
        try:
            if isinstance(expectation._mandatory_fields, str):
                # Parse JSON string from database
                mandatory_fields = json.loads(expectation._mandatory_fields)
            else:
                mandatory_fields = expectation._mandatory_fields
        except Exception as e:
            print(f"❌ Error parsing mandatory fields: {e}")
            mandatory_fields = {}
    else:
        print("ℹ️ No mandatory fields found or empty")

    print(f"🔍 DEBUG: Mandatory fields for user {user_id}: {mandatory_fields}")

    # Get current user to know gender
    current_user = Marriage.query.filter_by(user_id=user_id).first()
    if not current_user:
        print(f"❌ No marriage profile found for user {user_id}")
        return []

    user_gender = (current_user.gender or "").lower()
    print(f"🔍 DEBUG: Current user gender: {user_gender}")

    # Opposite gender profiles only
    if user_gender.startswith('male'):
        opposite_profiles = Marriage.query.filter(func.lower(func.trim(Marriage.gender)) == "female").all()
    elif user_gender.startswith('female'):
        opposite_profiles = Marriage.query.filter(func.lower(func.trim(Marriage.gender)) == "male").all()
    else:
        opposite_profiles = Marriage.query.filter(Marriage.gender != current_user.gender).all()

    print(f"🔍 DEBUG: Found {len(opposite_profiles)} opposite gender profiles")

    # 🚨 FIX: Initialize candidates list here
    candidates = []
    
    # Evaluate all opposite gender profiles
    for profile in opposite_profiles:
        print(f"\n--- Evaluating Profile {profile.user_id} ---")
        s = compute_expectation_score(expectation, profile, mandatory_fields)
        if s > 0:
            candidates.append({
                "user_id": profile.user_id,
                "name": profile.full_name,
                "gender": profile.gender,
                "location": profile.current_city,
                "religion": profile.religion,
                "remark": profile.remark,
                "expectation_score": s,
                "mandatory_matched": True
            })
            print(f"✅ Added candidate {profile.user_id} with score {s}")

    print(f"📈 Total candidates after mandatory filtering: {len(candidates)}")

    # 🚨 FIX: Get character compatibility for ALL candidates
    all_ids = [c["user_id"] for c in candidates]
    llm_data = LLMGeneratedQuestions.query.filter(LLMGeneratedQuestions.user_id.in_(all_ids)).all()
    llm_map = {l.user_id: (l.blue, l.green, l.yellow, l.red) for l in llm_data}

    # 🚨 FIX: Calculate character scores properly
    for c in candidates:
        if c["user_id"] in llm_map:
            b, g, y, r = llm_map[c["user_id"]]
            # Calculate character score as weighted sum of color percentages
            total = b + g + y + r
            if int(total) > 0:
                # Normalize and calculate similarity to ideal distribution
              
                char_score = calculate_character_similarity(b, g, y, r)
                c["character_score"] = round(char_score, 2)
            else:
                c["character_score"] = 0
        else:
            c["character_score"] = 0
        
        # Overall score combining both expectation and character
        c["overall_score"] = round(0.7 * c["expectation_score"] + 0.3 * c["character_score"], 2)

    # Return both sorted lists
    expectation_sorted = sorted(candidates, key=lambda x: x["expectation_score"], reverse=True)
    character_sorted = sorted(candidates, key=lambda x: x["character_score"], reverse=True)
    overall_sorted = sorted(candidates, key=lambda x: x["overall_score"], reverse=True)
    
    print(f"🎯 Final ranked by expectation: {len(expectation_sorted)}")
    print(f"🎯 Final ranked by character: {len(character_sorted)}")
    
    # 🚨 FIX: Return the appropriate list based on what the caller expects
    return expectation_sorted

def generate_expectation_explanation(expect_user: dict, profile_user: dict) -> list:
    """
    Compare user's expectations with another user's profile.
    Gives a clean, correct, field-by-field explanation.
    """

    explanations = []
    exact_matches = []
    differences = []
    missing_data = []

    # -------------------------------------------
    # 🔥 UNIVERSAL SAFE KEY LOOKUP
    # -------------------------------------------
    def get_profile_value(profile_dict, key_name):
        """Case-insensitive and alias-safe key lookup."""
        key_name = key_name.lower().strip()

        # Special aliases for country
        country_aliases = ["country", "location", "current_country",
                           "residence_country", "live_country"]

        for k, v in profile_dict.items():
            k_clean = k.lower().strip()

            # Match correct field
            if k_clean == key_name:
                return str(v).strip()

            # Match ANY country-related field
            if key_name == "country" and k_clean in country_aliases:
                return str(v).strip()

        # If not found
        return ""

    # -------------------------------------------
    # 🔥 FIELD MAPPING (Same as compute_expectation_score)
    # -------------------------------------------
    field_mapping = {
        'pref_age_range': 'date_of_birth',
        'pref_height_range': 'height',
        'pref_education_level': 'education_level',
        'pref_employment_status': 'employment_status',

        'pref_current_city': 'current_city',
        'pref_countries': 'country',        # 👉 FIXED HERE
        'pref_diet': 'food_preference',
        'pref_fitness': 'fitness_level',
        'pref_family_type': 'family_type',

        'accept_smoking': 'smoking_habit',
        'accept_alcohol': 'alcohol_habit',
        'pref_languages': 'languages_spoken',
        'religion_alignment': 'religion',
        'pref_partner_relocation': 'relocation_willingness',

        'pref_conflict_approach': 'conflict_approach',
        'pref_financial_style': 'financial_style',
        'pref_shared_hobbies': 'hobbies_interests',
        'travel_pref': 'travel_preference',
        'pet_pref': 'own_pets',
        
        'pref_income_range': 'income_range',
        'live_with_inlaws': 'live_with_inlaws',
        'pref_live_with_parents': 'live_with_parents',
        'financial_support_to_parents': 'support_parents_financially',
        'pref_career_aspirations': 'career_aspirations',

        'children_timeline': 'children_timeline',
        'open_to_adoption': 'open_to_adoption',
        'deal_breakers': 'deal_breakers',
        'other_non_negotiables': 'other_non_negotiables',
        'health_constraints': 'health_constraints',

        'skin_tone': 'skin_tone',
        'marital_status': 'marital_status',
        'daily_routine': 'daily_routine',
        'family_communication_frequency': 'family_communication_frequency',
        'relaxation_mode': 'relaxation_mode'
    }

    all_expectation_fields = list(field_mapping.keys())

    # -------------------------------------------
    # 🔥 FIELD COMPARISON LOGIC
    # -------------------------------------------
    for expect_key, profile_key in field_mapping.items():

        label = expect_key.replace("pref_", "").replace("_", " ").title()
        expect_value = str(expect_user.get(expect_key, "") or "").strip()

        # If no preference → skip
        if expect_value.lower() in ["", "no preference", "any", "all"]:
            continue

        # Correctly fetch profile value
        profile_value = get_profile_value(profile_user, profile_key)

        # Missing profile data (REAL missing only)
        if profile_value == "":
            missing_data.append((label, expect_value))
            continue

        # Perform match check
        if values_match(expect_value, profile_value, expect_key):
            exact_matches.append(f"• Profile matches your preference for {label.lower()} ({profile_value})")
        else:
            differences.append(
                f"• Profile differs from your preference for {label.lower()} "
                f"(you want: {expect_value}, they are: {profile_value})"
            )

    # -------------------------------------------
    # 🔥 COMPUTE COMPATIBILITY (Same as compute_expectation_score)
    # -------------------------------------------
    total_pref_fields = 0
    satisfied_count = 0

    for field_name in all_expectation_fields:
        expect_value = str(expect_user.get(field_name, "") or "").strip()
        if expect_value.lower() in ["", "no preference", "any", "all"]:
            continue

        total_pref_fields += 1
        profile_key = field_mapping[field_name]
        profile_value = get_profile_value(profile_user, profile_key)

        if profile_value and values_match(expect_value, profile_value, field_name):
            satisfied_count += 1

    if total_pref_fields > 0:
        percent = round((satisfied_count / total_pref_fields) * 100, 2)
    else:
        percent = 0

    # -------------------------------------------
    # 🔥 BUILD EXPLANATION OUTPUT
    # -------------------------------------------
    explanations.append(f"📊 **Expectation Compatibility**: {percent}%")
    explanations.append(f"• {satisfied_count} matches out of {total_pref_fields} preference fields")

    if len(missing_data) > 0:
        explanations.append(f"• ⚠️ {len(missing_data)} fields missing profile data")
        explanations.append("")
        explanations.append("**⚠️ Missing Profile Data:**")
        for label, expect_val in missing_data:
            explanations.append(f"• {label}: Profile missing (You want: {expect_val})")

    if len(exact_matches) > 0:
        explanations.append("")
        explanations.append("**🔍 Detailed Field Analysis:**")
        explanations.extend(exact_matches)
        explanations.extend(differences)

    return explanations