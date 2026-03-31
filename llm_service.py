import pyodbc
import os
import json
import uuid
import random
import threading

from datetime import datetime
# Add these imports if not already present
import re
from typing import Dict, List, Optional, Tuple, Any
from config import DEFAULT_N_QUESTIONS, DEFAULT_BATCH_SIZE, MAX_QUESTIONS, COLOR_KEYS, DOMAINS

# Try importing LLM libraries
try:
    from pydantic import BaseModel, Field
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
    from langchain_openai import ChatOpenAI
    HAS_LLM_STACK = True
    HAS_LLM = True
except Exception:
    HAS_LLM_STACK = False
    HAS_LLM = False


class Option(BaseModel):
    text: str
    color: str


class QAItem(BaseModel):
    question: str
    options: List[Option] = Field(min_items=4, max_items=4)


class BatchQA(BaseModel):
    items: List[QAItem] = Field(..., min_items=1)


# ==============================================
# UPDATED: SYSTEM_PROMPT with strict book-based options
# ==============================================
# SYSTEM_PROMPT = (
#     "You are creating personality assessment questions using the color personality system from the books.\n\n"
    
#     "🚨🚨🚨 ABSOLUTE RULES - NO EXCEPTIONS:\n"
#     "1) **NO FALLBACKS**: Use ONLY book examples provided below\n"
#     "2) **NO REPEATS**: Never repeat questions for the same user\n"
#     "3) **SIMPLE ENGLISH**: Use basic words everyone understands\n"
#     "   - Question: 15-20 words maximum, simple vocabulary\n"
#     "   - Option: 8-12 words maximum, very simple language\n"
#     "4) **DATA USAGE**:\n"
#     "   - PROFILE questions: Use RANDOM columns from ALL profile data\n"
#     "   - EXPECTATION questions: Use RANDOM columns from ALL expectation data\n"
#     "   - CHARACTER questions: GENERIC ONLY, NO user data references\n"
#     "5) **OPTIONS MUST USE BOOK CONCEPTS**: Only use the color concepts provided below\n\n"
    
#     "COLOR CONCEPTS FROM THE BOOK (USE THESE EXACTLY):\n"
#     "{faiss_color_behaviors}\n\n"
    
#     "Generate questions following ALL rules above:"
# )

SYSTEM_PROMPT = (
    "You are a character assessment engine for marriage compatibility.\n\n"

    "YOU MUST FOLLOW THESE RULES STRICTLY:\n"
    "1) You DO NOT define color meanings yourself\n"
    "2) You DO NOT invent personality traits\n"
    "3) You DO NOT explain colors\n"
    "4) ALL option behaviors MUST come ONLY from the provided book content\n"
    "5) If a behavior is not in the book content, DO NOT use it\n\n"

    "QUESTION RULES:\n"
    "- Questions must be character-based and situational\n"
    "- Do NOT repeat user words directly\n"
    "- Do NOT mention profile or expectation fields\n"
    "- Use abnormal or strong remarks as hints for framing questions\n\n"

    "OPTION RULES:\n"
    "- EXACTLY 4 options per question\n"
    "- One option per color: Red, Blue, Green, Yellow\n"
    "- Option text MUST be derived from BOOK BEHAVIORS ONLY\n"
    "- Do NOT describe what a color means\n\n"

    "BOOK-BASED COLOR BEHAVIORS (ONLY SOURCE OF TRUTH):\n"
    "{faiss_color_behaviors}\n\n"

    "Generate questions strictly following these rules."
)



# ==============================================
# UPDATED: USER_PROMPT_BATCH with strict requirements
# ==============================================

#simple question

# USER_PROMPT_BATCH = (
#     "### READ CAREFULLY – STRICT INSTRUCTIONS\n"
#     "You are generating CHARACTER ASSESSMENT QUESTIONS.\n\n"
 
#     "IMPORTANT:\n"
#     "- User data below is CONTEXT ONLY\n"
#     "- Do NOT quote or repeat user sentences\n"
#     "- Do NOT explain colors\n"
#     "- Do NOT use fallback or generic questions\n\n"
 
#     "QUESTION TYPE: {question_type}\n"
#     "NUMBER OF QUESTIONS: {n_questions}\n\n"
 
#     "SELECTION RULES:\n"
#     "- RANDOMLY select different aspects each time\n"
#     "- PROFILE: pick from ALL profile columns\n"
#     "- EXPECTATION: pick from ALL expectation columns\n"
#     "- Use abnormal or strong remarks as PRIORITY hints\n\n"
 
#     "OPTION RULES:\n"
#     "- EXACTLY 4 options\n"
#     "- Options MUST be derived ONLY from book behaviors below\n"
#     "- One option per color\n\n"
 
 
   
 
#     "### BOOK-BASED COLOR BEHAVIORS (USE ONLY THESE):\n"
#     "{faiss_color_behaviors}\n\n"
 
#     "### USER CONTEXT (READ ONLY – DO NOT COPY TEXT):\n"
#     "{user_context}\n\n"
 
#     "### PREVIOUS QUESTIONS (DO NOT REPEAT):\n"
#     "{previous_questions}\n\n"
 
#     "### HOW TO CREATE OPTIONS (USE BOOK CONCEPTS ABOVE):\n"
#     "For EACH question, create EXACTLY 4 options using the book concepts:\n"
#     "1) RED OPTION: Based on Red book behavior above\n"
#     "2) BLUE OPTION: Based on Blue book behavior above\n"
#     "3) GREEN OPTION: Based on Green book behavior above\n"
#     "4) YELLOW OPTION: Based on Yellow book behavior above\n\n"
   
#     "### SIMPLE ENGLISH EXAMPLES:\n"
#     "✅ GOOD QUESTION: 'When you need to make a quick choice, what do you do first?'\n"
#     "✅ GOOD OPTION: 'Look at all the facts first' (Blue concept)\n"
#     "❌ BAD OPTION: 'Engage in comprehensive analytical evaluation' (Too complex)\n\n"
   
#     "### REMEMBER:\n"
#     "- Simple words only\n"
#     "- No repeats\n"
#     "- Use book concepts for options\n"
#     "- Different questions for each user\n\n"
#     "{format_instructions}\n\n"
#     "Generate {question_type} questions now:"
# )
 
#with the columns word

USER_PROMPT_BATCH = (
    "### READ CAREFULLY – STRICT INSTRUCTIONS\n"
    "You are generating CHARACTER ASSESSMENT QUESTIONS for MARRIAGE COMPATIBILITY.\n\n"

    "IMPORTANT:\n"
    "- User data below is CONTEXT ONLY\n"
    "- Do NOT quote or repeat user sentences\n"
    "- Do NOT explain colors\n"
    "- Do NOT use fallback or generic questions\n"
    "- Do NOT ask abstract personality or life questions\n\n"

    "QUESTION TYPE: {question_type}\n"
    "NUMBER OF QUESTIONS: {n_questions}\n\n"

    "SELECTION RULES:\n"
    "- RANDOMLY select different aspects each time\n"
    "- PROFILE: pick from ALL profile columns\n"
    "- EXPECTATION: pick from ALL expectation columns\n"
    "- Use abnormal or strong remarks as PRIORITY hints\n\n"

    "### DERIVATION RULE (MOST IMPORTANT):\n"
    "For EVERY question you generate:\n"
    "1) Pick ONE specific STATEMENT from the USER CONTEXT\n"
    "2) Identify an underlying expectation, rigidity, habit, or assumption\n"
    "3) Convert it into a TRADE-OFF, FLEXIBILITY, or TOLERANCE question\n\n"

    "Transformations you MUST apply:\n"
    "- Requirement → tolerance\n"
    "- Preference → compromise\n"
    "- Expectation → adjustment limit\n"
    "- Habit → adaptability\n"
    "- Boundary → flexibility\n\n"

    "STRICTLY FORBIDDEN:\n"
    "- Generic personality questions\n"
    "- Abstract life questions\n"
    "- Questions not traceable to a user statement\n"
    "- Copying or paraphrasing user sentences\n\n"

    "OPTION RULES:\n"
    "- EXACTLY 4 options\n"
    "- Options MUST be derived ONLY from book behaviors below\n"
    "- One option per color\n\n"

    "### BOOK-BASED COLOR BEHAVIORS (USE ONLY THESE):\n"
    "{faiss_color_behaviors}\n\n"

    "### USER CONTEXT (READ ONLY – EACH QUESTION MUST BE DERIVED FROM ONE STATEMENT):\n"
    "{user_context}\n\n"

    "### PREVIOUS QUESTIONS (DO NOT REPEAT):\n"
    "{previous_questions}\n\n"

    "### HOW TO CREATE OPTIONS (USE BOOK CONCEPTS ABOVE):\n"
    "For EACH question, create EXACTLY 4 options using the book concepts:\n"
    "1) RED OPTION: Based on Red book behavior above\n"
    "2) BLUE OPTION: Based on Blue book behavior above\n"
    "3) GREEN OPTION: Based on Green book behavior above\n"
    "4) YELLOW OPTION: Based on Yellow book behavior above\n\n"

    "### SIMPLE ENGLISH ONLY:\n"
    "✅ GOOD QUESTION:\n"
    "'You value financial stability. How do you react if your partner takes a risky career step?'\n\n"
    "❌ BAD QUESTION:\n"
    "'How do you feel about risk in life?'\n\n"

    "### REMEMBER:\n"
    "- Each question MUST be tied to ONE user statement\n"
    "- Frame questions as compatibility stress-tests\n"
    "- Simple English only\n"
    "- No repeats\n"
    "- Options ONLY from book concepts\n\n"

    "{format_instructions}\n\n"
    "Generate {question_type} questions now:"
)





PARSER_BATCH = None
CHAIN_BATCH = None

if HAS_LLM_STACK and os.getenv("OPENAI_API_KEY"):
    try:
        PARSER_BATCH = PydanticOutputParser(pydantic_object=BatchQA)

        def build_batch_chain():
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.7,
                max_retries=2,
                timeout=30,
                model_kwargs={"response_format": {"type": "json_object"}},
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROMPT),
                    ("user", USER_PROMPT_BATCH),
                ]
            )
            return prompt | llm | PARSER_BATCH

        CHAIN_BATCH = build_batch_chain()
    except Exception as e:
        print("Failed to build CHAIN_BATCH:", e)
        CHAIN_BATCH = None


def build_randomized_user_context(all_user_data: Dict, question_type: str) -> str:
    """
    Builds READ-ONLY context for the LLM.
    - Uses ALL columns
    - Randomly selects aspects
    - PRIORITIZES abnormal remarks
    - This is NOT a question prompt
    """

    context_parts: List[str] = []

    profile_data = all_user_data.get("profile", {})
    expectation_data = all_user_data.get("expectation", {})
    unusual_hints = all_user_data.get("unusual_hints", [])

    # ===============================
    # PROFILE CONTEXT
    # ===============================
    if question_type == "profile" and profile_data:
        keys = [
            k for k in profile_data.keys()
            if k not in ("user_id", "id", "created_at", "updated_at")
            and str(profile_data.get(k)).strip()
        ]

        random.shuffle(keys)
        selected_keys = keys[:5]

        context_parts.append("### PROFILE CONTEXT (RANDOMLY SELECTED ASPECTS)")
        context_parts.append(
            "These describe the user's background, habits, and self-described traits."
        )

        for k in selected_keys:
            context_parts.append(f"- STATEMENT ({k}): {profile_data[k]}")


    # ===============================
    # EXPECTATION CONTEXT
    # ===============================
    elif question_type == "expectation" and expectation_data:
        keys = [
            k for k in expectation_data.keys()
            if k not in ("user_id", "id", "created_at", "updated_at", "_mandatory_fields")
            and str(expectation_data.get(k)).strip()
        ]

        random.shuffle(keys)
        selected_keys = keys[:5]

        context_parts.append("### EXPECTATION CONTEXT (RANDOMLY SELECTED ASPECTS)")
        context_parts.append(
            "These describe what the user expects from a life partner or relationship."
        )

        for k in selected_keys:
            context_parts.append(f"- {k}: {expectation_data[k]}")

    # ===============================
    # CHARACTER CONTEXT (GENERIC)
    # ===============================
    elif question_type == "character":
        context_parts.append(
            "### GENERIC CHARACTER CONTEXT\n"
            "Do NOT use any user data.\n"
            "Generate general personality questions only."
        )

    # ===============================
    # PRIORITY: UNUSUAL / ABNORMAL REMARKS
    # ===============================
    if unusual_hints:
        context_parts.append(
            "\n### CRITICAL REMARKS (HIGH PRIORITY HINTS)\n"
            "These indicate strong, unusual, emotional, or extreme character traits.\n"
            "Use them as PRIMARY HINTS when framing questions.\n"
            "DO NOT repeat these sentences directly."
        )

        for hint in unusual_hints:
            context_parts.append(
                f"- {hint['source']}::{hint['field']}: {hint['value']}"
            )

    return "\n".join(context_parts)




def summarize_profile(profile: Dict) -> Dict:
    """Extract all non-PII columns from Marriage table for LLM context"""
    out: Dict = {}

    # All columns from Marriage table (excluding PII where possible)
    marriage_columns = [
        "user_id",
        "full_name",
        "gender",
        "current_city",
        "marital_status",
        "education_level",
        "employment_status",
        "number_of_siblings",
        "family_type",
        "hobbies_interests",
        "conflict_approach",
        "financial_style",
        "income_range",
        "relocation_willingness",
        "height",
        "skin_tone",
        "languages_spoken",
        "country",
        "blood_group",
        "religion",
        "dual_citizenship",
        "siblings_position",
        "parents_living_status",
        "live_with_parents",
        "support_parents_financially",
        "family_communication_frequency",
        "food_preference",
        "smoking_habit",
        "alcohol_habit",
        "daily_routine",
        "fitness_level",
        "own_pets",
        "travel_preference",
        "relaxation_mode",
        "job_role",
        "work_experience_years",
        "career_aspirations",
        "field_of_study",
        "remark",
        "children_timeline",
        "open_to_adoption",
        "deal_breakers",
        "other_non_negotiables",
        "health_constraints",
        "live_with_inlaws",
    ]

    for col in marriage_columns:
        v = profile.get(col)
        if v not in (None, "", []):
            out[col] = v

    return out


def offline_generate_batch(themes: List[str], state: Dict, context: str = "") -> List[Dict]:
    """Raise error - no offline fallback allowed"""
    raise Exception("LLM service is required. Offline generation is disabled.")





def extract_all_user_data(user_id: str, role: str) -> Dict[str, Dict]:
    """Extract ALL columns from both Marriage and ExpectationResponse tables"""
    
    try:
        from database import get_db_connection
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        all_data = {
            "profile": {},
            "expectation": {},
            "unusual_hints": []
        }
        
        # ==============================================
        # 1. Get ALL columns from Marriage table (Profile)
        # ==============================================
        cur.execute(f"""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Marriage' 
            ORDER BY ORDINAL_POSITION
        """)
        marriage_columns = [row[0] for row in cur.fetchall()]
        
        if marriage_columns:
            # Get user's data for all columns
            placeholders = ', '.join(['?'] * len(marriage_columns))
            cur.execute(f"""
                SELECT {', '.join(marriage_columns)}
                FROM Marriage 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cur.fetchone()
            if row:
                for i, col in enumerate(marriage_columns):
                    value = row[i]
                    if value is not None and str(value).strip():
                        all_data["profile"][col] = value
                        
                        # Check for unusual/remarkable entries
                        if col in ["remark", "other_non_negotiables", "deal_breakers"]:
                            if value and str(value).strip().lower() not in ["none", "na", "not specified", ""]:
                                all_data["unusual_hints"].append({
                                    "source": "profile",
                                    "field": col,
                                    "value": str(value)[:200]  # Limit length
                                })
        
        # ==============================================
        # 2. Get ALL columns from ExpectationResponse table
        # ==============================================
        cur.execute(f"""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'ExpectationResponse' 
            ORDER BY ORDINAL_POSITION
        """)
        expectation_columns = [row[0] for row in cur.fetchall()]
        
        if expectation_columns:
            # Get user's data for all columns
            placeholders = ', '.join(['?'] * len(expectation_columns))
            cur.execute(f"""
                SELECT {', '.join(expectation_columns)}
                FROM ExpectationResponse 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cur.fetchone()
            if row:
                for i, col in enumerate(expectation_columns):
                    value = row[i]
                    if value is not None and str(value).strip():
                        all_data["expectation"][col] = value
                        
                        # Check for unusual/remarkable entries
                        if col in ["deal_breakers", "other_non_negotiables", "expectation_summary"]:
                            if value and str(value).strip().lower() not in ["none", "na", "not specified", ""]:
                                all_data["unusual_hints"].append({
                                    "source": "expectation", 
                                    "field": col,
                                    "value": str(value)[:200]
                                })
        
        conn.close()
        
        print(f"✅ DEBUG: Extracted {len(all_data['profile'])} profile columns, "
              f"{len(all_data['expectation'])} expectation columns, "
              f"{len(all_data['unusual_hints'])} unusual hints")
        
        return all_data
        
    except Exception as e:
        print(f"❌ Error extracting user data: {e}")
        return {"profile": {}, "expectation": {}, "unusual_hints": []}








def get_items_from_result(result):
    """Helper to extract items from LLM result"""
    if hasattr(result, "items"):
        return result.items
    elif isinstance(result, dict) and "items" in result:
        return result["items"]
    else:
        return []



def debug_faiss_content():
    """Debug function to see what's actually in FAISS"""
    try:
        from faiss_service import knowledge
        
        if not knowledge or not knowledge.sources:
            print("❌ No knowledge sources available")
            return
        
        print("\n🔍 DEBUGGING FAISS CONTENT")
        print("=" * 50)
        
        for source in knowledge.sources:
            print(f"\n📚 Source: {source.name}")
            print(f"   Meta entries: {len(source.meta)}")
            
            # Show first few entries
            for i, item in enumerate(source.meta[:5]):
                text = item.get("text", "")[:100] + "..." if len(item.get("text", "")) > 100 else item.get("text", "")
                concept_type = item.get("concept_type", "none")
                book_name = item.get("book_name", "unknown")
                print(f"   {i+1}. Type: {concept_type}, Book: {book_name}")
                print(f"      Text: {text}")
        
        print("=" * 50)
        
        # Try a simple search to see what we get
        print("\n🔍 Testing simple searches:")
        for color in ["red", "blue", "green", "yellow"]:
            print(f"\n  Searching for '{color}':")
            results = knowledge.search(
                query=f"{color} personality",
                topk=3,
                max_chars=100
            )
            if results:
                for j, result in enumerate(results):
                    text = result.get("text", "")[:80]
                    source = result.get("source", "unknown")
                    print(f"    {j+1}. [{source}] {text}...")
            else:
                print(f"    ❌ No results for '{color}'")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")  



# llm_service.py - REPLACE THE ENTIRE get_book_based_color_behaviors FUNCTION

def get_book_based_color_behaviors(question_text: str, question_type: str) -> Dict[str, List[str]]:
    """REAL RAG: Search ALL books for color personality content"""
    
    print(f"🔍 REAL RAG: Searching ALL books for {question_type.upper()} behaviors...")
    
    color_behaviors = {
        "red": [],
        "blue": [], 
        "green": [],
        "yellow": []
    }
    
    try:
        from faiss_service import knowledge
        
        if not knowledge or not knowledge.is_ready():
            print("❌ Knowledge base not ready")
            raise Exception("Knowledge base not ready")
        
        print(f"✅ Knowledge base ready with {len(knowledge.loader.documents) if knowledge.loader else 0} documents")
        
        # Use the specialized search method
        for color in ["red", "blue", "green", "yellow"]:
            print(f"\n🔍 Searching for '{color.upper()}' personality behavior in ALL books...")
            
            try:
                results = knowledge.search_color_personality(
                    color=color,
                    behavior_type="personality",
                    topk=3
                )
                
                if results:
                    for i, result in enumerate(results):
                        text = result.get("text", "")
                        book_name = result.get("book_name", "")
                        
                        if text:
                            formatted = f"{text}"
                            if book_name:
                                formatted += f" (from {book_name})"
                            
                            color_behaviors[color].append(formatted)
                            print(f"    ✅ Found: {text[:80]}...")
                else:
                    print(f"    ⚠️ No {color} behavior found in books")
                    
            except Exception as color_error:
                print(f"    ❌ Error searching for {color}: {color_error}")
                continue
        
        # Print summary
        print(f"\n📊 RAG RESULTS FROM ALL BOOKS:")
        for color in ["red", "blue", "green", "yellow"]:
            count = len(color_behaviors[color])
            print(f"  {color.upper()}: {count} behaviors")
        
        return color_behaviors
        
    except Exception as e:
        print(f"❌ RAG search failed: {e}")
        import traceback
        traceback.print_exc()
        raise Exception(f"RAG failed: {str(e)}")


def extract_behavioral_sentences_from_text(text: str, color: str) -> List[str]:
    """Extract behavioral sentences from text"""
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    behavioral_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 25 <= len(sentence) <= 120:
            sentence_lower = sentence.lower()
            
            # Check for behavioral language
            behavioral_indicators = [
                "tends to", "typically", "usually", "often",
                "behaves", "acts", "prefers", "likes",
                "characteristic", "trait", "personality"
            ]
            
            if any(indicator in sentence_lower for indicator in behavioral_indicators):
                # Check if it's relevant to the color
                color_keywords = {
                    "red": ["assertive", "dominant", "competitive", "decisive", "leadership"],
                    "blue": ["analytical", "detail", "systematic", "logical", "precise"],
                    "green": ["patient", "cooperative", "supportive", "peaceful", "team"],
                    "yellow": ["optimistic", "creative", "enthusiastic", "social", "energetic"]
                }
                
                keywords = color_keywords.get(color, [])
                if any(keyword in sentence_lower for keyword in keywords):
                    behavioral_sentences.append(sentence)
    
    return behavioral_sentences[:3]


# llm_service.py - ADD THIS NEW FUNCTION

def create_color_behavior_prompt(color_behaviors: Dict[str, List[str]]) -> str:
    """Create a structured prompt for LLM with book-based color behaviors"""
    
    prompt_parts = []
    
    prompt_parts.append("COLOR PERSONALITY BEHAVIORS FROM BOOKS:")
    prompt_parts.append("=" * 60)
    
    for color in ["red", "blue", "green", "yellow"]:
        color_name = color.upper()
        behaviors = color_behaviors.get(color, [])
        
        prompt_parts.append(f"\n{color_name} PERSONALITY:")
        
        if behaviors:
            for i, behavior in enumerate(behaviors, 1):
                # Clean the behavior text
                clean_behavior = behavior.replace('\n', ' ').strip()
                prompt_parts.append(f"  {i}. {clean_behavior}")
        else:
            prompt_parts.append(f"  [Book does not contain specific {color} behavior info]")
    
    prompt_parts.append("=" * 60)
    prompt_parts.append("\nINSTRUCTIONS FOR CREATING OPTIONS:")
    prompt_parts.append("1. RED OPTION: Should reflect direct, decisive, results-oriented behavior")
    prompt_parts.append("2. BLUE OPTION: Should reflect analytical, precise, systematic behavior")
    prompt_parts.append("3. GREEN OPTION: Should reflect patient, supportive, cooperative behavior")
    prompt_parts.append("4. YELLOW OPTION: Should reflect optimistic, creative, social behavior")
    prompt_parts.append("\nEXAMPLES OF SIMPLE OPTIONS BASED ON BOOK:")
    prompt_parts.append("- Red: 'Take immediate action to solve the problem'")
    prompt_parts.append("- Blue: 'Carefully analyze all the details first'")
    prompt_parts.append("- Green: 'Discuss with others to find a peaceful solution'")
    prompt_parts.append("- Yellow: 'Think of creative new ways to approach this'")
    
    return "\n".join(prompt_parts)





def clean_rag_result(text: str, color: str) -> str:
    """Clean RAG retrieval results"""
    
    # Remove citations, references
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\([^)]*\d{4}[^)]*\)', '', text)
    
    # Fix OCR errors
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Check if it's meaningful
    if len(text) < 20 or len(text) > 200:
        return ""
    
    # Check for relevance
    text_lower = text.lower()
    
    # Should contain behavioral or personality terms
    relevant_terms = [
        "behavior", "personality", "trait", "characteristic",
        "tends", "typically", "usually", "often", "prefers"
    ]
    
    if not any(term in text_lower for term in relevant_terms):
        return ""
    
    return text


def calculate_relevance_score(text: str, color: str) -> float:
    """Calculate relevance score for RAG results"""
    
    text_lower = text.lower()
    score = 0.0
    
    # Direct color mention (highest score)
    if color in text_lower or f"{color} " in text_lower:
        score += 1.0
    
    # Behavioral language
    behavioral_terms = ["tends to", "typically", "usually", "often", "behaves"]
    if any(term in text_lower for term in behavioral_terms):
        score += 0.5
    
    # Personality terms
    if "personality" in text_lower or "trait" in text_lower:
        score += 0.3
    
    # Length factor (optimal 50-120 chars)
    if 50 <= len(text) <= 120:
        score += 0.2
    
    return min(score, 1.0)  # Cap at 1.0


def reformulate_as_color_behavior(text: str, color: str, concept: str) -> str:
    """Reformulate general text as color behavior"""
    
    sentences = re.split(r'[.!?]\s+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 30 <= len(sentence) <= 100:
            sentence_lower = sentence.lower()
            
            # Check if it contains the concept
            if concept in sentence_lower:
                # Reformulate to mention color
                return f"A {color} personality {sentence_lower}".capitalize()
    
    return ""


def extract_color_relevant_sentences(text: str, color: str) -> List[str]:
    """Extract sentences relevant to a color from general text"""
    
    sentences = re.split(r'[.!?]\s+', text)
    relevant = []
    
    # Color to trait mapping
    color_traits = {
        "red": ["assertive", "dominant", "competitive", "decisive", "leader"],
        "blue": ["analytical", "detailed", "perfectionist", "systematic", "logical"],
        "green": ["cooperative", "patient", "supportive", "peaceful", "team"],
        "yellow": ["optimistic", "creative", "social", "enthusiastic", "energetic"]
    }
    
    traits = color_traits.get(color, [])
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 25 <= len(sentence) <= 120:
            sentence_lower = sentence.lower()
            
            # Check for trait mentions
            if any(trait in sentence_lower for trait in traits):
                relevant.append(sentence)
            
            # Check for behavioral patterns
            elif any(word in sentence_lower for word in ["tends to", "typically", "usually"]):
                relevant.append(sentence)
    
    return relevant[:2]  # Return at most 2 sentences






def extract_relevant_sentence(text: str, search_hint: str, color: str) -> str:
    """Extract the sentence most relevant to the search hint"""
    
    # Clean and split text
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'[.!?]\s+', text)
    
    # Score each sentence based on relevance to hint
    best_sentence = ""
    best_score = 0
    
    hint_words = set(search_hint.lower().split())
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 20 <= len(sentence) <= 120:
            sentence_lower = sentence.lower()
            
            # Calculate relevance score
            score = 0
            
            # 1. Check for hint word matches
            sentence_words = set(sentence_lower.split())
            common_words = hint_words.intersection(sentence_words)
            score += len(common_words) * 3
            
            # 2. Check for behavioral language
            behavioral_indicators = ["tends", "typically", "usually", "often", "behaves", "prefers"]
            if any(word in sentence_lower for word in behavioral_indicators):
                score += 2
            
            # 3. Check for color relevance
            color_keywords = {
                "red": ["assertive", "dominant", "competitive", "decisive", "leader"],
                "blue": ["analytical", "detailed", "perfectionist", "systematic", "logical"],
                "green": ["patient", "cooperative", "supportive", "peaceful", "team"],
                "yellow": ["optimistic", "creative", "social", "enthusiastic", "energetic"]
            }
            
            if any(word in sentence_lower for word in color_keywords.get(color, [])):
                score += 2
            
            # 4. Check for direct color mention
            if color in sentence_lower:
                score += 1
            
            if score > best_score:
                best_score = score
                best_sentence = sentence
    
    if best_score >= 2:  # Minimum relevance threshold
        return best_sentence.capitalize()
    
    return ""


def extract_behavioral_sentence(text: str) -> str:
    """Extract any behavioral sentence from text"""
    
    sentences = re.split(r'[.!?]\s+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 25 <= len(sentence) <= 100:
            sentence_lower = sentence.lower()
            
            # Look for behavioral patterns
            behavioral_patterns = [
                "tends to", "typically", "usually", "often",
                "behaves", "acts", "prefers", "likes",
                "characteristic", "trait", "personality"
            ]
            
            if any(pattern in sentence_lower for pattern in behavioral_patterns):
                return sentence.capitalize()
    
    return ""


def extract_colors_from_disc_text(text: str) -> Dict[str, List[str]]:
    """Extract all color behaviors from DISC system text"""
    
    colors = {
        "red": [],
        "blue": [],
        "green": [],
        "yellow": []
    }
    
    # Look for color sections
    text_lower = text.lower()
    
    # Common DISC patterns
    disc_patterns = [
        (r"red[^.]*?(?:tends to|typically|usually|often|behaves|acts)[^.]*\.", "red"),
        (r"blue[^.]*?(?:tends to|typically|usually|often|behaves|acts)[^.]*\.", "blue"),
        (r"green[^.]*?(?:tends to|typically|usually|often|behaves|acts)[^.]*\.", "green"),
        (r"yellow[^.]*?(?:tends to|typically|usually|often|behaves|acts)[^.]*\.", "yellow")
    ]
    
    for pattern, color in disc_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            sentence = match.strip()
            if len(sentence) > 20:
                colors[color].append(sentence.capitalize())
    
    return colors





def extract_any_personality_sentence(text: str, color: str) -> str:
    """Extract any personality-related sentence as last resort"""
    
    sentences = re.split(r'[.!?]\s+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 30 <= len(sentence) <= 150:
            sentence_lower = sentence.lower()
            
            # Personality keywords
            personality_words = [
                "personality", "behavior", "trait", "characteristic",
                "temperament", "disposition", "nature", "style"
            ]
            
            if any(word in sentence_lower for word in personality_words):
                return f"{sentence} (general personality)"
    
    return ""


def debug_faiss_content_specific():
    """Debug what's actually searchable in FAISS"""
    
    print("\n🔍 DEBUGGING FAISS CONTENT STRUCTURE:")
    print("=" * 60)
    
    try:
        from faiss_service import knowledge
        
        if not knowledge or not knowledge.sources:
            print("❌ No knowledge sources")
            return
        
        # Test what kinds of queries return results
        test_queries = [
            ("personality", "general personality"),
            ("behavior", "behavior terms"),
            ("communication", "communication styles"),
            ("DISC", "DISC system"),
            ("red blue green yellow", "color mentions"),
            ("assertive", "specific trait"),
            ("analytical", "another trait")
        ]
        
        for query, description in test_queries:
            print(f"\n🔍 Testing: '{query}' ({description})...")
            
            try:
                results = knowledge.search(
                    query=query,
                    topk=2,
                    max_chars=100
                )
                
                if results:
                    for i, result in enumerate(results):
                        source = result.get("source", "unknown")
                        text = result.get("text", "")[:80]
                        print(f"  {i+1}. [{source}] {text}...")
                else:
                    print(f"  ❌ No results for '{query}'")
                    
            except Exception as e:
                print(f"  ⚠️ Search failed: {e}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")


def extract_disc_behavior_from_text(text: str, color: str) -> str:
    """Extract DISC behavior from Surrounded by Idiots text"""
    
    # Clean text
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Look for DISC-specific patterns
    sentences = re.split(r'[.!?]\s+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 20 <= len(sentence) <= 100:
            sentence_lower = sentence.lower()
            
            # Check for color mention + behavioral language
            color_patterns = [
                f"{color} ",
                f"{color} type",
                f"{color} person",
                f"{color} people",
                f"the {color}s"
            ]
            
            mentions_color = any(pattern in sentence_lower for pattern in color_patterns)
            is_behavioral = any(word in sentence_lower for word in 
                               ["behaves", "acts", "tends", "typically", "usually", 
                                "often", "prefers", "likes", "characteristic", "trait"])
            
            if mentions_color and is_behavioral:
                return f"{sentence} (from Surrounded by Idiots)"
    
    return ""


def extract_academic_behavior_from_text(text: str, color: str) -> str:
    """Extract behavioral psychology from PyMatch Books"""
    
    # Clean academic text
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\(\w+,\s*\d{4}\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    sentences = re.split(r'[.!?]\s+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if 25 <= len(sentence) <= 120:
            sentence_lower = sentence.lower()
            
            # Look for psychological behavioral terms
            if any(word in sentence_lower for word in 
                  ["behavior", "personality", "trait", "characteristic", 
                   "tends to", "often", "typically"]):
                
                # Map to DISC colors
                color_keywords = {
                    "red": ["assertive", "dominant", "competitive", "decisive", "leadership"],
                    "blue": ["analytical", "perfectionist", "detail", "systematic", "precise"],
                    "green": ["agreeable", "cooperative", "patient", "supportive", "team"],
                    "yellow": ["extraverted", "creative", "enthusiastic", "social", "optimistic"]
                }
                
                keywords = color_keywords.get(color, [])
                if any(keyword in sentence_lower for keyword in keywords):
                    return f"{sentence} (from PyMatch Books)"
    
    return ""



def extract_color_behavior(text: str, color: str) -> str:
    """Extract a clean behavioral sentence about the color"""
    
    # Split into sentences
    sentences = re.split(r'[.!?]\s+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue
        
        sentence_lower = sentence.lower()
        
        # Check if sentence mentions the color
        mentions_color = (
            color in sentence_lower or 
            f"{color} personality" in sentence_lower or
            f"{color} type" in sentence_lower or
            f"{color} people" in sentence_lower
        )
        
        # Check for behavioral language
        is_behavioral = any(
            word in sentence_lower 
            for word in ["behavior", "behaves", "acts", "tends", "typically", 
                        "usually", "often", "personality", "trait", "characteristic"]
        )
        
        if mentions_color and is_behavioral:
            # Clean the sentence
            clean_sentence = re.sub(r'\s+', ' ', sentence).strip()
            if 20 <= len(clean_sentence) <= 150:
                return clean_sentence
        
        # If no direct color mention but has behavioral content about relevant traits
        elif is_behavioral:
            # Check for color-relevant keywords
            color_keywords = {
                "red": ["dominant", "assertive", "competitive", "decisive", "leadership"],
                "blue": ["analytical", "perfectionist", "detail", "systematic", "precise"],
                "green": ["agreeable", "cooperative", "patient", "supportive", "team"],
                "yellow": ["extraverted", "creative", "enthusiastic", "social", "optimistic"]
            }
            
            if any(keyword in sentence_lower for keyword in color_keywords.get(color, [])):
                clean_sentence = re.sub(r'\s+', ' ', sentence).strip()
                if 20 <= len(clean_sentence) <= 150:
                    return f"People with {color}-like traits {clean_sentence.lower()}"
    
    return ""


def clean_academic_text(text: str) -> str:
    """Clean OCR'd academic text"""
    
    if not text:
        return ""
    
    # Remove citations like [12], (Smith, 2020), etc.
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\([^)]*\d{4}[^)]*\)', '', text)
    text = re.sub(r'\b\d{4}\b', '', text)  # Remove standalone years
    
    # Fix common OCR errors
    replacements = {
        "hu man": "human",
        "psy chological": "psychological",
        "be haviour": "behaviour",
        "tem perament": "temperament",
        "char acter": "character",
        "fun damental": "fundamental"
    }
    
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text



# def generate_batch_questions(
#     themes: List[str],
#     state: Dict,
#     context: str = "",
#     previous_questions: List[str] = None
# ) -> List[Dict]:
#     print("=" * 60)
#     print("🚀 STARTING QUESTION GENERATION WITH RETRY LOGIC")
#     print("=" * 60)
    
#     # Get user data
#     profile = state.get("profile", {})
#     expectation = state.get("expectation", {})
#     user_id = profile.get("user_id", "")
    
#     if not user_id:
#         print("❌ ERROR: No user_id in state")
#         raise Exception("User ID is required")
    
#     print(f"👤 Generating for user: {user_id}")
    
#     # LLM MUST BE AVAILABLE
#     if CHAIN_BATCH is None or PARSER_BATCH is None:
#         print("❌ CRITICAL: LLM service not available")
#         raise Exception("LLM service required - no fallback")
    
#     try:
#         all_items: List[Dict] = []
#         previous_questions = previous_questions or []
        
#         print(f"📋 Previous questions: {len(previous_questions)}")
        
#         # ==============================================
#         # 1. PROFILE QUESTIONS (5 questions) - WITH RETRY
#         # ==============================================
#         print("\n" + "=" * 40)
#         print("📝 GENERATING 5 PROFILE QUESTIONS")
#         print("=" * 40)

#         # Build context with ALL profile columns
#         profile_context_lines = []
#         profile_context_lines.append("### ALL PROFILE DATA (USE THIS FULL DATA FOR QUESTIONS):")
#         profile_context_lines.append("Create EXACTLY 5 personalized questions based on ALL fields below:")
        
#         # Add ALL profile columns
#         for field, value in profile.items():
#             if value is not None and str(value).strip() and field not in ["user_id", "created_at", "updated_at", "id"]:
#                 profile_context_lines.append(f"- {field}: {value}")
        
#         profile_context = "\n".join(profile_context_lines)

#         # Get ACTUAL book behaviors
#         print(f"🔍 Getting ACTUAL book behaviors for profile questions...")
#         profile_behaviors = get_book_based_color_behaviors("profile questions", "profile")
#         formatted_behaviors = create_color_behavior_prompt(profile_behaviors)

#         # Generate questions - WITH RETRY IF NEEDED
#         profile_items = []
#         retry_count = 0
#         max_retries = 2
        
#         while len(profile_items) < 5 and retry_count < max_retries:
#             if retry_count > 0:
#                 print(f"🔄 RETRY {retry_count}: Need {5 - len(profile_items)} more profile questions")
            
#             profile_prompt = {
#                 "faiss_color_behaviors": formatted_behaviors,
#                 "question_type": "profile",
#                 "n_questions": str(5 - len(profile_items)) if retry_count > 0 else "5",
#                 "user_context": profile_context + f"\n\n### IMPORTANT: Generate EXACTLY {5 - len(profile_items) if retry_count > 0 else 5} questions. Each must be unique and personalized.",
#                 "previous_questions": json.dumps(previous_questions, ensure_ascii=False),
#                 "format_instructions": PARSER_BATCH.get_format_instructions(),
#             }

#             print(f"🤖 Calling LLM for profile questions (attempt {retry_count + 1})...")
#             result = CHAIN_BATCH.invoke(profile_prompt)
#             new_items = get_items_from_result(result)
            
#             # Convert Pydantic models to dictionaries
#             processed_items = []
#             for item in new_items:
#                 if hasattr(item, "dict"):
#                     processed_items.append(item.dict())
#                 elif isinstance(item, dict):
#                     processed_items.append(item)
#                 else:
#                     # Try to convert
#                     try:
#                         processed_items.append(dict(item))
#                     except:
#                         continue
            
#             # Add unique items only
#             existing_questions = [q.get("question", "").lower() for q in profile_items]
#             for item in processed_items:
#                 question = item.get("question", "").lower()
#                 if question and question not in existing_questions and len(profile_items) < 5:
#                     profile_items.append(item)
#                     existing_questions.append(question)
            
#             retry_count += 1
        
#         print(f"✅ Generated {len(profile_items)} profile questions")
        
#         # Process exactly 5 profile questions
#         for i, item in enumerate(profile_items[:5]):
#             out = item.copy() if isinstance(item, dict) else item.dict()
            
#             # Validate
#             if len(out.get("options", [])) != 4:
#                 print(f"❌ ERROR: Question {i+1} has {len(out['options'])} options")
#                 out["options"] = [
#                     {"text": "Analyze all details carefully", "color": "blue"},
#                     {"text": "Follow a step-by-step plan", "color": "green"},
#                     {"text": "Take immediate action", "color": "red"},
#                     {"text": "Think of creative new ideas", "color": "yellow"}
#                 ]
            
#             # Ensure simple English
#             out["options"] = ensure_simple_options(out.get("options", []))
            
#             # Check for duplicates
#             question_text = out.get("question", "").lower()
#             if question_text in previous_questions:
#                 out["question"] = out["question"] + " (based on your profile)"
            
#             # Add metadata
#             out["source"] = "llm_profile_all_data"
#             out["question_type"] = "profile"
#             out["book_based"] = True
#             out["simple_english"] = are_options_simple(out.get("options", []))
            
#             all_items.append(out)
#             previous_questions.append(out["question"])
#             print(f"  ✅ Profile Q{i+1}: {out['question'][:60]}...")
        
#         # ==============================================
#         # 2. EXPECTATION QUESTIONS (5 questions) - WITH RETRY
#         # ==============================================
#         print("\n" + "=" * 40)
#         print("💭 GENERATING 5 EXPECTATION QUESTIONS")
#         print("=" * 40)
        
#         # Build context with ALL expectation columns
#         expectation_context_lines = []
#         expectation_context_lines.append("### ALL EXPECTATION DATA (USE THIS FULL DATA FOR QUESTIONS):")
#         expectation_context_lines.append("Create EXACTLY 5 personalized questions based on ALL expectation fields below:")
        
#         # Add ALL expectation columns
#         for field, value in expectation.items():
#             if value is not None and str(value).strip() and field not in ["user_id", "created_at", "updated_at", "id", "_mandatory_fields"]:
#                 expectation_context_lines.append(f"- {field}: {value}")
        
#         expectation_context = "\n".join(expectation_context_lines)
        
#         # Get ACTUAL book behaviors
#         print(f"🔍 Getting ACTUAL book behaviors for expectation questions...")
#         expectation_behaviors = get_book_based_color_behaviors("expectation questions", "expectation")
#         formatted_behaviors = create_color_behavior_prompt(expectation_behaviors)
        
#         # Generate questions - WITH RETRY IF NEEDED
#         expectation_items = []
#         retry_count = 0
        
#         while len(expectation_items) < 5 and retry_count < max_retries:
#             if retry_count > 0:
#                 print(f"🔄 RETRY {retry_count}: Need {5 - len(expectation_items)} more expectation questions")
            
#             expectation_prompt = {
#                 "faiss_color_behaviors": formatted_behaviors,
#                 "question_type": "expectation",
#                 "n_questions": str(5 - len(expectation_items)) if retry_count > 0 else "5",
#                 "user_context": expectation_context + f"\n\n### IMPORTANT: Generate EXACTLY {5 - len(expectation_items) if retry_count > 0 else 5} questions. Each must be unique and personalized.",
#                 "previous_questions": json.dumps(previous_questions, ensure_ascii=False),
#                 "format_instructions": PARSER_BATCH.get_format_instructions(),
#             }
            
#             print(f"🤖 Calling LLM for expectation questions (attempt {retry_count + 1})...")
#             result = CHAIN_BATCH.invoke(expectation_prompt)
#             new_items = get_items_from_result(result)
            
#             # Convert Pydantic models to dictionaries
#             processed_items = []
#             for item in new_items:
#                 if hasattr(item, "dict"):
#                     processed_items.append(item.dict())
#                 elif isinstance(item, dict):
#                     processed_items.append(item)
#                 else:
#                     try:
#                         processed_items.append(dict(item))
#                     except:
#                         continue
            
#             # Add unique items only
#             existing_questions = [q.get("question", "").lower() for q in expectation_items]
#             for item in processed_items:
#                 question = item.get("question", "").lower()
#                 if question and question not in existing_questions and len(expectation_items) < 5:
#                     expectation_items.append(item)
#                     existing_questions.append(question)
            
#             retry_count += 1
        
#         print(f"✅ Generated {len(expectation_items)} expectation questions")
        
#         # Process exactly 5 expectation questions
#         for i, item in enumerate(expectation_items[:5]):
#             out = item.copy() if isinstance(item, dict) else item.dict()
            
#             # Validate
#             if len(out.get("options", [])) != 4:
#                 out["options"] = [
#                     {"text": "Look at all facts carefully", "color": "blue"},
#                     {"text": "Follow clear rules and steps", "color": "green"},
#                     {"text": "Take charge and act quickly", "color": "red"},
#                     {"text": "Think of new possibilities", "color": "yellow"}
#                 ]
            
#             # Ensure simple English
#             out["options"] = ensure_simple_options(out.get("options", []))
            
#             # Check for duplicates
#             question_text = out.get("question", "").lower()
#             if question_text in previous_questions:
#                 out["question"] = out["question"] + " (in relationships)"
            
#             # Add metadata
#             out["source"] = "llm_expectation_all_data"
#             out["question_type"] = "expectation"
#             out["book_based"] = True
#             out["simple_english"] = are_options_simple(out.get("options", []))
            
#             all_items.append(out)
#             previous_questions.append(out["question"])
#             print(f"  ✅ Expectation Q{i+1}: {out['question'][:60]}...")
        
#         # ==============================================
#         # 3. CHARACTER QUESTIONS (10 questions) - WITH RETRY
#         # ==============================================
#         print("\n" + "=" * 40)
#         print("🧠 GENERATING 10 CHARACTER QUESTIONS (GENERIC)")
#         print("=" * 40)
        
#         # Generic context
#         character_context = (
#             "### IMPORTANT: Generate EXACTLY 10 generic personality questions\n"
#             "DO NOT use any user data from below.\n"
#             "Create general personality questions that apply to anyone.\n"
#             "Each question should cover different aspects of personality.\n\n"
#             "### SUGGESTED TOPICS (choose different ones):\n"
#             f"{', '.join(themes[:20] if themes else ['decision making', 'stress', 'communication', 'work', 'learning', 'conflict', 'planning', 'creativity', 'teamwork', 'change'])}\n\n"
#             "### USER DATA (DO NOT USE - FOR REFERENCE ONLY):\n"
#             "[Data available but must not be referenced]"
#         )
        
#         # Get ACTUAL book behaviors
#         print(f"🔍 Getting ACTUAL book behaviors for character questions...")
#         character_behaviors = get_book_based_color_behaviors("character questions", "character")
#         formatted_behaviors = create_color_behavior_prompt(character_behaviors)
        
#         # Generate questions - WITH RETRY IF NEEDED
#         character_items = []
#         retry_count = 0
        
#         while len(character_items) < 10 and retry_count < max_retries:
#             if retry_count > 0:
#                 print(f"🔄 RETRY {retry_count}: Need {10 - len(character_items)} more character questions")
            
#             character_prompt = {
#                 "faiss_color_behaviors": formatted_behaviors,
#                 "question_type": "character",
#                 "n_questions": str(10 - len(character_items)) if retry_count > 0 else "10",
#                 "user_context": character_context + f"\n\n### CRITICAL: Generate EXACTLY {10 - len(character_items) if retry_count > 0 else 10} questions. NO FEWER.",
#                 "previous_questions": json.dumps(previous_questions, ensure_ascii=False),
#                 "format_instructions": PARSER_BATCH.get_format_instructions(),
#             }
            
#             print(f"🤖 Calling LLM for character questions (attempt {retry_count + 1})...")
#             result = CHAIN_BATCH.invoke(character_prompt)
#             new_items = get_items_from_result(result)
            
#             # Convert Pydantic models to dictionaries
#             processed_items = []
#             for item in new_items:
#                 if hasattr(item, "dict"):
#                     processed_items.append(item.dict())
#                 elif isinstance(item, dict):
#                     processed_items.append(item)
#                 else:
#                     try:
#                         processed_items.append(dict(item))
#                     except:
#                         continue
            
#             # Add unique items only
#             existing_questions = [q.get("question", "").lower() for q in character_items]
#             for item in processed_items:
#                 question = item.get("question", "").lower()
#                 if question and question not in existing_questions and len(character_items) < 10:
#                     character_items.append(item)
#                     existing_questions.append(question)
            
#             retry_count += 1
        
#         print(f"✅ Generated {len(character_items)} character questions")
        
#         # Process exactly 10 character questions
#         for i, item in enumerate(character_items[:10]):
#             out = item.copy() if isinstance(item, dict) else item.dict()
            
#             # Validate
#             if len(out.get("options", [])) != 4:
#                 out["options"] = [
#                     {"text": "Analyze carefully before deciding", "color": "blue"},
#                     {"text": "Follow a clear organized method", "color": "green"},
#                     {"text": "Act quickly and decisively", "color": "red"},
#                     {"text": "Think of innovative approaches", "color": "yellow"}
#                 ]
            
#             # Ensure simple English
#             out["options"] = ensure_simple_options(out.get("options", []))
            
#             # Check for user-specific references
#             question_lower = out.get("question", "").lower()
#             if any(word in question_lower for word in ["your ", "you are ", "as a ", "your "]):
#                 out["question"] = out["question"].replace("your ", "people's ")
#                 out["question"] = out["question"].replace("you are ", "people are ")
#                 out["question"] = out["question"].replace("you ", "people ")
            
#             # Check for duplicates
#             if question_lower in previous_questions:
#                 out["question"] = out["question"] + " (personality aspect)"
            
#             # Add metadata
#             out["source"] = "llm_character_generic_book_based"
#             out["question_type"] = "character"
#             out["book_based"] = True
#             out["generic"] = True
#             out["simple_english"] = are_options_simple(out.get("options", []))
            
#             all_items.append(out)
#             previous_questions.append(out["question"])
#             print(f"  ✅ Character Q{i+11}: {out['question'][:60]}...")
        
#         # ==============================================
#         # FINAL VALIDATION
#         # ==============================================
#         print("\n" + "=" * 60)
#         print("✅ FINAL VALIDATION")
#         print("=" * 60)
        
#         # Check distribution
#         profile_count = sum(1 for q in all_items if q.get("question_type") == "profile")
#         expectation_count = sum(1 for q in all_items if q.get("question_type") == "expectation")
#         character_count = sum(1 for q in all_items if q.get("question_type") == "character")
        
#         print(f"📊 Distribution: Profile={profile_count}, Expectation={expectation_count}, Character={character_count}")
#         print(f"📊 Total questions: {len(all_items)}/20")
        
#         # If still not 20, raise error
#         if len(all_items) != 20:
#             print(f"❌ ERROR: Only {len(all_items)} questions generated by LLM")
#             raise Exception(f"LLM failed to generate 20 questions. Got {len(all_items)} questions.")
        
#         print("=" * 60)
#         print(f"🎉 SUCCESS: Generated 20 questions from LLM for user {user_id}")
#         print("=" * 60)
        
#         return all_items[:20]
        
#     except Exception as e:
#         print(f"\n❌❌❌ QUESTION GENERATION FAILED ❌❌❌")
#         print(f"Error: {e}")
#         import traceback
#         traceback.print_exc()
#         print("=" * 60)
#         raise Exception(f"Question generation failed: {str(e)}")



def generate_batch_questions(
    themes: List[str],
    state: Dict,
    context: str = "",
    previous_questions: List[str] = None
) -> List[Dict]:
    print("=" * 60)
    print("🚀 STARTING QUESTION GENERATION WITH RETRY LOGIC")
    print("=" * 60)
    
    # Get user data
    profile = state.get("profile", {})
    expectation = state.get("expectation", {})
    user_id = profile.get("user_id", "")
    
    if not user_id:
        print("❌ ERROR: No user_id in state")
        raise Exception("User ID is required")
    
    print(f"👤 Generating for user: {user_id}")
    
    # LLM MUST BE AVAILABLE
    if CHAIN_BATCH is None or PARSER_BATCH is None:
        print("❌ CRITICAL: LLM service not available")
        raise Exception("LLM service required - no fallback")
    
    try:
        all_items: List[Dict] = []
        previous_questions = previous_questions or []
        
        print(f"📋 Previous questions: {len(previous_questions)}")
        
        # ==============================================
        # 1. PROFILE QUESTIONS (5 questions) - WITH RETRY
        # ==============================================
        print("\n" + "=" * 40)
        print("📝 GENERATING 5 PROFILE QUESTIONS")
        print("=" * 40)

        # Build context with ALL profile columns
        profile_context_lines = []
        profile_context_lines.append("### ALL PROFILE DATA (USE THIS FULL DATA FOR QUESTIONS):")
        profile_context_lines.append("Create EXACTLY 5 personalized questions based on ALL fields below:")
        
        # Add ALL profile columns
        for field, value in profile.items():
            if value is not None and str(value).strip() and field not in ["user_id", "created_at", "updated_at", "id"]:
                profile_context_lines.append(f"- {field}: {value}")
        
        profile_context = "\n".join(profile_context_lines)

        # Get ACTUAL book behaviors
        print(f"🔍 Getting ACTUAL book behaviors for profile questions...")
        profile_behaviors = get_book_based_color_behaviors("profile questions", "profile")
        formatted_behaviors = create_color_behavior_prompt(profile_behaviors)

        # Generate questions - WITH RETRY IF NEEDED
        profile_items = []
        retry_count = 0
        max_retries = 2
        
        while len(profile_items) < 5 and retry_count < max_retries:
            if retry_count > 0:
                print(f"🔄 RETRY {retry_count}: Need {5 - len(profile_items)} more profile questions")
            
            profile_prompt = {
                "faiss_color_behaviors": formatted_behaviors,
                "question_type": "profile",
                "n_questions": str(5 - len(profile_items)) if retry_count > 0 else "5",
                "user_context": profile_context + f"\n\n### IMPORTANT: Generate EXACTLY {5 - len(profile_items) if retry_count > 0 else 5} questions. Each must be unique and personalized.",
                "previous_questions": json.dumps(previous_questions, ensure_ascii=False),
                "format_instructions": PARSER_BATCH.get_format_instructions(),
            }

            print(f"🤖 Calling LLM for profile questions (attempt {retry_count + 1})...")
            result = CHAIN_BATCH.invoke(profile_prompt)
            new_items = get_items_from_result(result)
            
            # Convert Pydantic models to dictionaries
            processed_items = []
            for item in new_items:
                if hasattr(item, "dict"):
                    processed_items.append(item.dict())
                elif isinstance(item, dict):
                    processed_items.append(item)
                else:
                    # Try to convert
                    try:
                        processed_items.append(dict(item))
                    except:
                        continue
            
            # Add unique items only
            existing_questions = [q.get("question", "").lower() for q in profile_items]
            for item in processed_items:
                question = item.get("question", "").lower()
                if question and question not in existing_questions and len(profile_items) < 5:
                    profile_items.append(item)
                    existing_questions.append(question)
            
            retry_count += 1
        
        print(f"✅ Generated {len(profile_items)} profile questions")
        
        # Process exactly 5 profile questions
        for i, item in enumerate(profile_items[:5]):
            out = item.copy() if isinstance(item, dict) else item.dict()
            
            # Validate
            if len(out.get("options", [])) != 4:
                print(f"❌ ERROR: Question {i+1} has {len(out['options'])} options")
                out["options"] = [
                    {"text": "Analyze all details carefully", "color": "blue"},
                    {"text": "Follow a step-by-step plan", "color": "green"},
                    {"text": "Take immediate action", "color": "red"},
                    {"text": "Think of creative new ideas", "color": "yellow"}
                ]
            
            # Ensure simple English
            out["options"] = ensure_simple_options(out.get("options", []))
            
            # Check for duplicates
            question_text = out.get("question", "").lower()
            if question_text in previous_questions:
                out["question"] = out["question"] + " (based on your profile)"
            
            # Add metadata
            out["source"] = "llm_profile_all_data"
            out["question_type"] = "profile"
            out["book_based"] = True
            out["simple_english"] = are_options_simple(out.get("options", []))
            
            all_items.append(out)
            previous_questions.append(out["question"])
            print(f"  ✅ Profile Q{i+1}: {out['question'][:60]}...")
        
        # ==============================================
        # 2. EXPECTATION QUESTIONS (5 questions) - WITH RETRY
        # ==============================================
        print("\n" + "=" * 40)
        print("💭 GENERATING 5 EXPECTATION QUESTIONS")
        print("=" * 40)
        
        # Build context with ALL expectation columns
        expectation_context_lines = []
        expectation_context_lines.append("### ALL EXPECTATION DATA (USE THIS FULL DATA FOR QUESTIONS):")
        expectation_context_lines.append("Create EXACTLY 5 personalized questions based on ALL expectation fields below:")
        
        # Add ALL expectation columns
        for field, value in expectation.items():
            if value is not None and str(value).strip() and field not in ["user_id", "created_at", "updated_at", "id", "_mandatory_fields"]:
                expectation_context_lines.append(f"- {field}: {value}")
        
        expectation_context = "\n".join(expectation_context_lines)
        
        # Get ACTUAL book behaviors
        print(f"🔍 Getting ACTUAL book behaviors for expectation questions...")
        expectation_behaviors = get_book_based_color_behaviors("expectation questions", "expectation")
        formatted_behaviors = create_color_behavior_prompt(expectation_behaviors)
        
        # Generate questions - WITH RETRY IF NEEDED
        expectation_items = []
        retry_count = 0
        
        while len(expectation_items) < 5 and retry_count < max_retries:
            if retry_count > 0:
                print(f"🔄 RETRY {retry_count}: Need {5 - len(expectation_items)} more expectation questions")
            
            expectation_prompt = {
                "faiss_color_behaviors": formatted_behaviors,
                "question_type": "expectation",
                "n_questions": str(5 - len(expectation_items)) if retry_count > 0 else "5",
                "user_context": expectation_context + f"\n\n### IMPORTANT: Generate EXACTLY {5 - len(expectation_items) if retry_count > 0 else 5} questions. Each must be unique and personalized.",
                "previous_questions": json.dumps(previous_questions, ensure_ascii=False),
                "format_instructions": PARSER_BATCH.get_format_instructions(),
            }
            
            print(f"🤖 Calling LLM for expectation questions (attempt {retry_count + 1})...")
            result = CHAIN_BATCH.invoke(expectation_prompt)
            new_items = get_items_from_result(result)
            
            # Convert Pydantic models to dictionaries
            processed_items = []
            for item in new_items:
                if hasattr(item, "dict"):
                    processed_items.append(item.dict())
                elif isinstance(item, dict):
                    processed_items.append(item)
                else:
                    try:
                        processed_items.append(dict(item))
                    except:
                        continue
            
            # Add unique items only
            existing_questions = [q.get("question", "").lower() for q in expectation_items]
            for item in processed_items:
                question = item.get("question", "").lower()
                if question and question not in existing_questions and len(expectation_items) < 5:
                    expectation_items.append(item)
                    existing_questions.append(question)
            
            retry_count += 1
        
        print(f"✅ Generated {len(expectation_items)} expectation questions")
        
        # Process exactly 5 expectation questions
        for i, item in enumerate(expectation_items[:5]):
            out = item.copy() if isinstance(item, dict) else item.dict()
            
            # Validate
            if len(out.get("options", [])) != 4:
                out["options"] = [
                    {"text": "Look at all facts carefully", "color": "blue"},
                    {"text": "Follow clear rules and steps", "color": "green"},
                    {"text": "Take charge and act quickly", "color": "red"},
                    {"text": "Think of new possibilities", "color": "yellow"}
                ]
            
            # Ensure simple English
            out["options"] = ensure_simple_options(out.get("options", []))
            
            # Check for duplicates
            question_text = out.get("question", "").lower()
            if question_text in previous_questions:
                out["question"] = out["question"] + " (in relationships)"
            
            # Add metadata
            out["source"] = "llm_expectation_all_data"
            out["question_type"] = "expectation"
            out["book_based"] = True
            out["simple_english"] = are_options_simple(out.get("options", []))
            
            all_items.append(out)
            previous_questions.append(out["question"])
            print(f"  ✅ Expectation Q{i+1}: {out['question'][:60]}...")
        
        # ==============================================
        # 3. CHARACTER QUESTIONS (10 questions) - WITH RETRY
        # ==============================================
        print("\n" + "=" * 40)
        print("🧠 GENERATING 10 CHARACTER QUESTIONS (GENERIC)")
        print("=" * 40)
        
        # Generic context
        character_context = (
            "### IMPORTANT: Generate EXACTLY 10 generic personality questions\n"
            "DO NOT use any user data from below.\n"
            "Create general personality questions that apply to anyone.\n"
            "Each question should cover different aspects of personality.\n\n"
            "### SUGGESTED TOPICS (choose different ones):\n"
            f"{', '.join(themes[:20] if themes else ['decision making', 'stress', 'communication', 'work', 'learning', 'conflict', 'planning', 'creativity', 'teamwork', 'change'])}\n\n"
            "### USER DATA (DO NOT USE - FOR REFERENCE ONLY):\n"
            "[Data available but must not be referenced]"
        )
        
        # Get ACTUAL book behaviors
        print(f"🔍 Getting ACTUAL book behaviors for character questions...")
        character_behaviors = get_book_based_color_behaviors("character questions", "character")
        formatted_behaviors = create_color_behavior_prompt(character_behaviors)
        
        # Generate questions - WITH RETRY IF NEEDED
        character_items = []
        retry_count = 0
        
        while len(character_items) < 10 and retry_count < max_retries:
            if retry_count > 0:
                print(f"🔄 RETRY {retry_count}: Need {10 - len(character_items)} more character questions")
            
            character_prompt = {
                "faiss_color_behaviors": formatted_behaviors,
                "question_type": "character",
                "n_questions": str(10 - len(character_items)) if retry_count > 0 else "10",
                "user_context": character_context + f"\n\n### CRITICAL: Generate EXACTLY {10 - len(character_items) if retry_count > 0 else 10} questions. NO FEWER.",
                "previous_questions": json.dumps(previous_questions, ensure_ascii=False),
                "format_instructions": PARSER_BATCH.get_format_instructions(),
            }
            
            print(f"🤖 Calling LLM for character questions (attempt {retry_count + 1})...")
            result = CHAIN_BATCH.invoke(character_prompt)
            new_items = get_items_from_result(result)
            
            # Convert Pydantic models to dictionaries
            processed_items = []
            for item in new_items:
                if hasattr(item, "dict"):
                    processed_items.append(item.dict())
                elif isinstance(item, dict):
                    processed_items.append(item)
                else:
                    try:
                        processed_items.append(dict(item))
                    except:
                        continue
            
            # Add unique items only
            existing_questions = [q.get("question", "").lower() for q in character_items]
            for item in processed_items:
                question = item.get("question", "").lower()
                if question and question not in existing_questions and len(character_items) < 10:
                    character_items.append(item)
                    existing_questions.append(question)
            
            retry_count += 1
        
        print(f"✅ Generated {len(character_items)} character questions")
        
        # Process exactly 10 character questions
        for i, item in enumerate(character_items[:10]):
            out = item.copy() if isinstance(item, dict) else item.dict()
            
            # Validate
            if len(out.get("options", [])) != 4:
                out["options"] = [
                    {"text": "Analyze carefully before deciding", "color": "blue"},
                    {"text": "Follow a clear organized method", "color": "green"},
                    {"text": "Act quickly and decisively", "color": "red"},
                    {"text": "Think of innovative approaches", "color": "yellow"}
                ]
            
            # Ensure simple English
            out["options"] = ensure_simple_options(out.get("options", []))
            
            # Check for user-specific references
            question_lower = out.get("question", "").lower()
            if any(word in question_lower for word in ["your ", "you are ", "as a ", "your "]):
                out["question"] = out["question"].replace("your ", "people's ")
                out["question"] = out["question"].replace("you are ", "people are ")
                out["question"] = out["question"].replace("you ", "people ")
            
            # Check for duplicates
            if question_lower in previous_questions:
                out["question"] = out["question"] + " (personality aspect)"
            
            # Add metadata
            out["source"] = "llm_character_generic_book_based"
            out["question_type"] = "character"
            out["book_based"] = True
            out["generic"] = True
            out["simple_english"] = are_options_simple(out.get("options", []))
            
            all_items.append(out)
            previous_questions.append(out["question"])
            print(f"  ✅ Character Q{i+11}: {out['question'][:60]}...")
        
        # ==============================================
        # FINAL VALIDATION
        # ==============================================
        print("\n" + "=" * 60)
        print("✅ FINAL VALIDATION")
        print("=" * 60)
        
        # Check distribution
        profile_count = sum(1 for q in all_items if q.get("question_type") == "profile")
        expectation_count = sum(1 for q in all_items if q.get("question_type") == "expectation")
        character_count = sum(1 for q in all_items if q.get("question_type") == "character")
        
        print(f"📊 Distribution: Profile={profile_count}, Expectation={expectation_count}, Character={character_count}")
        print(f"📊 Total questions: {len(all_items)}/20")
        
        # If still not 20, raise error
        if len(all_items) != 20:
            print(f"❌ ERROR: Only {len(all_items)} questions generated by LLM")
            raise Exception(f"LLM failed to generate 20 questions. Got {len(all_items)} questions.")
        
        print("=" * 60)
        print(f"🎉 SUCCESS: Generated 20 questions from LLM for user {user_id}")
        print("=" * 60)
        
        return all_items[:20]
        
    except Exception as e:
        print(f"\n❌❌❌ QUESTION GENERATION FAILED ❌❌❌")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        raise Exception(f"Question generation failed: {str(e)}")






# ==============================================
# UPDATED: ensure_simple_options (stricter)
# ==============================================
def ensure_simple_options(options: List[Dict]) -> List[Dict]:
    """Ensure options use very simple English"""
    
    simple_options = []
    
    for option in options:
        text = option.get("text", "")
        color = option.get("color", "")
        
        # Simplify aggressively
        simple_text = simplify_text_aggressive(text)
        
        # Word count check
        words = simple_text.split()
        if len(words) > 15:  # Too long
            # Keep first 12 words
            simple_text = " ".join(words[:12]) + "..."
        
        simple_options.append({
            "text": simple_text[:100],  # Max 100 chars
            "color": color
        })
    
    return simple_options

# ==============================================
# NEW: simplify_text_aggressive
# ==============================================
def simplify_text_aggressive(text: str) -> str:
    """Aggressively simplify text for basic English"""
    
    if not text:
        return text
    
    # Convert to lowercase for processing
    lower_text = text.lower()
    
    # Common complex word replacements
    replacements = {
        # Complex to simple
        "implement": "do",
        "utilize": "use",
        "facilitate": "help",
        "optimize": "improve",
        "analyze": "look at",
        "evaluate": "check",
        "systematically": "step by step",
        "methodically": "carefully",
        "innovative": "new",
        "conceptualize": "think of",
        "scrutinize": "examine",
        "meticulously": "very carefully",
        "envision": "imagine",
        "comprehensive": "complete",
        "initiate": "start",
        "subsequently": "then",
        "approximately": "about",
        "demonstrate": "show",
        "consequently": "so",
        "nevertheless": "but",
        "furthermore": "also",
        "moreover": "also",
        "therefore": "so",
        "thus": "so",
        "hence": "so",
        "accordingly": "so",
        
        # Simplify phrases
        "in order to": "to",
        "with regard to": "about",
        "on a regular basis": "regularly",
        "at this point in time": "now",
        "due to the fact that": "because",
        "in the event that": "if",
        "prior to": "before",
        "subsequent to": "after",
    }
    
    simple_text = text
    for complex_word, simple_word in replacements.items():
        # Case insensitive replacement
        pattern = re.compile(re.escape(complex_word), re.IGNORECASE)
        simple_text = pattern.sub(simple_word, simple_text)
    
    # Remove extra spaces
    simple_text = re.sub(r'\s+', ' ', simple_text).strip()
    
    # Ensure it ends with period
    if simple_text and not simple_text.endswith(('.', '!', '?')):
        simple_text += '.'
    
    print(f"  🔤 Simplified: '{text[:50]}...' -> '{simple_text[:50]}...'")
    return simple_text




# ==============================================
# UPDATED: are_options_simple (stricter)
# ==============================================
def are_options_simple(options: List[Dict]) -> bool:
    """Check if options use very simple English"""
    
    if not options:
        return False
    
    # Complex words that should NOT appear
    complex_words = [
        "implement", "utilize", "facilitate", "optimize", "analyze",
        "evaluate", "systematically", "methodically", "innovative",
        "conceptualize", "scrutinize", "meticulously", "comprehensive",
        "initiate", "subsequently", "approximately", "demonstrate",
        "consequently", "nevertheless", "furthermore", "moreover",
        "therefore", "thus", "hence", "accordingly"
    ]
    
    for option in options:
        text = option.get("text", "").lower()
        
        # Check for complex words
        for word in complex_words:
            if word in text:
                print(f"  ⚠️ Complex word '{word}' found in option")
                return False
        
        # Check word count
        words = text.split()
        if len(words) > 15:
            print(f"  ⚠️ Option too long: {len(words)} words")
            return False
    
    return True

# ==============================================
# UPDATED: offline_generate_batch (NO FALLBACK)
# ==============================================
def offline_generate_batch(themes: List[str], state: Dict, context: str = "") -> List[Dict]:
    """Raise error - NO OFFLINE FALLBACK ALLOWED"""
    print("❌❌❌ OFFLINE GENERATION ATTEMPTED - NOT ALLOWED ❌❌❌")
    raise Exception("LLM service is REQUIRED. Offline generation is DISABLED.")



# ==============================================
# UPDATED: SessionState with question tracking
# ==============================================
class SessionState:
    def __init__(
        self,
        n_questions: int,
        batch_size: int,
        domain: str = "general",
        role: Optional[str] = None,
        profile: Optional[Dict] = None,
        expectation: Optional[Dict] = None,
    ):
        domain = (domain or role or "general").lower()
        self.domain = domain if domain in DOMAINS else "general"
        self.role = role or self.domain
        self.profile = profile or {}
        self.expectation = expectation or {}
        self.n_questions = max(1, min(n_questions, MAX_QUESTIONS))
        self.batch_size = max(1, batch_size)
        self.asked = 0
        self.color_counts = {c: 0 for c in COLOR_KEYS}
        self.history: List[Dict] = []
        self.queue: List[Dict] = []
        self.finished = False
        
        # Track ALL asked questions to prevent repeats
        self.all_asked_questions: List[str] = []
        # Track per-user to prevent cross-user repeats (if needed)
        self.user_id = profile.get("user_id", "") if profile else ""
        
        print(f"📝 Session created for user: {self.user_id}")
        print(f"📝 Will track {self.n_questions} total questions")

    def to_min_state(self) -> Dict:
        total = sum(self.color_counts.values()) or 1
        mix_percentages = {
            k: round((v / total) * 100, 2) for k, v in self.color_counts.items()
        }
        dominant = max(self.color_counts, key=self.color_counts.get) if total else None
        
        # ✅ Summarize BOTH profile and expectation
        profile_summary = summarize_profile(self.profile)
        expectation_summary = summarize_expectation(self.expectation)  # Need to create this function
        
        return {
            "asked": self.asked,
            "dominant": dominant,
            "mix": mix_percentages,
            "domain": self.domain,
            "role": self.role,
            "profile": profile_summary,
            "expectation": expectation_summary,  # ✅ Add expectation to state
        }



    def remaining(self) -> int:
        return self.n_questions - self.asked


SESSIONS_FILE = os.getenv("PYMATCH_SESSIONS_FILE", "sessions.json")
_sessions_lock = threading.Lock()
SESSIONS: Dict[str, SessionState] = {}


def save_sessions():
    try:
        with _sessions_lock:
            serializable = {sid: s.__dict__ for sid, s in SESSIONS.items()}
            tmp = SESSIONS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, SESSIONS_FILE)
    except Exception as e:
        print("Failed to save sessions:", e)



def summarize_expectation(expectation: Dict) -> Dict:
    """Extract all non-PII columns from ExpectationResponse table for LLM context"""
    out: Dict = {}
    
    if not expectation:
        return out
    
    # All columns from ExpectationResponse table (excluding PII where possible)
    expectation_columns = [
        "user_id",
        "deal_breakers",
        "other_non_negotiables",
        "expectation_summary",
        "conflict_approach_expectation",
        "financial_expectations",
        "work_life_balance",
        "family_involvement",
        "religious_practices",
        "social_life",
        "personal_space",
        "communication_style",
        "decision_making",
        "leisure_activities",
        "health_lifestyle",
        "career_support",
        "parenting_approach",
        "conflict_resolution",
        "trust_boundaries",
        "shared_responsibilities",
        "created_at",
        "updated_at"
    ]
    
    for col in expectation_columns:
        v = expectation.get(col)
        if v not in (None, "", []):
            out[col] = v
    
    return out




def persist_final_progress(user_id: Optional[str], role: str, mix: Dict[str, float]) -> bool:
    from database import get_db_connection
    from config import PROGRESS_TBL

    llm_id = str(uuid.uuid4())
    blue = float(mix.get("blue", 0.0))
    green = float(mix.get("green", 0.0))
    yellow = float(mix.get("yellow", 0.0))
    red = float(mix.get("red", 0.0))
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Try with llm_id; if identity error, retry without it
        try:
            cur.execute(
                f"""
                INSERT INTO [dbo].[{PROGRESS_TBL}]
                  ([llm_id],[user_id],[role],[blue],[green],[yellow],[red],[created_at])
                VALUES (?,?,?,?,?,?,?,SYSUTCDATETIME())
            """,
                (
                    llm_id,
                    str(user_id) if user_id is not None else None,
                    role,
                    blue,
                    green,
                    yellow,
                    red,
                ),
            )
            conn.commit()
            return True
        except pyodbc.Error as e:
            if "IDENTITY_INSERT" in str(e) or "(544)" in str(e):
                cur.execute(
                    f"""
                    INSERT INTO [dbo].[{PROGRESS_TBL}]
                      ([user_id],[role],[blue],[green],[yellow],[red],[created_at])
                    VALUES (?,?,?,?,?,?,SYSUTCDATETIME())
                """,
                    (
                        str(user_id) if user_id is not None else None,
                        role,
                        blue,
                        green,
                        yellow,
                        red,
                    ),
                )
                conn.commit()
                return True
            else:
                print("Persist failed:", e)
                return False
    except Exception as ex:
        print("Persist final progress failed:", ex)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def choose_themes(sess, k: int) -> List[str]:
    """Choose k themes, preferably from FAISS TEXT_CHUNKS, else generic list."""
    try:
        from faiss_service import HAS_FAISS, FAISS_INDEX, TEXT_CHUNKS

        if HAS_FAISS and FAISS_INDEX is not None and TEXT_CHUNKS:
            # Just grab k random chunks from the indexed document
            selected = random.sample(TEXT_CHUNKS, min(k, len(TEXT_CHUNKS)))
            # Wrap them as "themes" but really they are just context text
            return selected
    except ImportError:
        pass

    # fallback: use generic themes
    fallback_themes = [
        "communication style",
        "conflict resolution",
        "decision making",
        "problem solving",
        "team collaboration",
        "personal values",
        "work habits",
        "social interaction",
        "stress management",
        "goal setting",
        "time management",
        "relationship dynamics",
    ]
    return random.sample(fallback_themes, min(k, len(fallback_themes)))


def analyze_actual_book_content():
    """See what behavioral content is actually in your books"""
    
    print("\n🔍 ANALYZING ACTUAL BOOK CONTENT")
    print("=" * 60)
    
    try:
        from faiss_service import knowledge
        
        if not knowledge or not knowledge.sources:
            print("❌ No knowledge sources")
            return
        
        # Test what kind of content exists
        test_searches = [
            ("behavior psychology", "general behavioral concepts"),
            ("personality traits", "personality characteristics"),
            ("communication styles", "how people communicate"),
            ("decision making", "how decisions are made"),
            ("social interaction", "how people interact"),
            ("emotional responses", "how people react emotionally")
        ]
        
        for search_term, description in test_searches:
            print(f"\n🔍 '{search_term}' ({description}):")
            
            results = knowledge.search(
                query=search_term,
                topk=2,
                source_names=["PyMatch Books", "Surrounded by Idiots"],
                max_chars=120
            )
            
            if results:
                for i, result in enumerate(results):
                    source = result.get("source", "")
                    text = result.get("text", "")
                    print(f"  {i+1}. [{source}] {text[:100]}...")
            else:
                print(f"  ❌ No results")
    
    except Exception as e:
        print(f"❌ Analysis failed: {e}")




def verify_book_content_quality():
    """Verify that books contain personality behavior content"""
    
    print("\n🔍 VERIFYING BOOK CONTENT QUALITY")
    print("=" * 60)
    
    try:
        from faiss_service import knowledge
        
        if not knowledge or not knowledge.is_ready():
            print("❌ Knowledge base not ready")
            return
        
        # Test each color
        for color in ["red", "blue", "green", "yellow"]:
            print(f"\n🔍 Testing '{color.upper()}' content:")
            
            # Test direct search
            results = knowledge.search(
                query=f"{color} personality behavior traits",
                topk=2,
                max_chars=100
            )
            
            if results:
                print(f"  ✅ Found {len(results)} results")
                for i, result in enumerate(results):
                    source = result.get("source", "unknown")
                    text = result.get("text", "")[:80]
                    print(f"    {i+1}. [{source}] {text}...")
            else:
                print(f"  ❌ No direct results for '{color}'")
                
                # Try broader search
                broader_results = knowledge.search(
                    query="behavior personality traits",
                    topk=1,
                    max_chars=100
                )
                
                if broader_results:
                    print(f"  ⚠️ Found general personality content")
                else:
                    print(f"  ❌ No personality content found at all")
    
    except Exception as e:
        print(f"❌ Verification failed: {e}")


def debug_faiss_content():
    """Debug what's in the combined index"""
    
    try:
        from faiss_service import knowledge
        
        if not knowledge or not knowledge.loader:
            print("❌ No knowledge source available")
            return
        
        print("\n🔍 DEBUGGING COMBINED INDEX")
        print("=" * 50)
        
        print(f"📚 Total documents: {len(knowledge.loader.documents)}")
        
        # Show books available
        books = set()
        for doc in knowledge.loader.documents[:20]:  # Check first 20
            book = doc.get("book", "Unknown")
            books.add(book)
        
        print(f"📚 Books in index: {', '.join(list(books))}")
        
        # Show first few entries
        print("\n📄 Sample documents:")
        for i, doc in enumerate(knowledge.loader.documents[:5]):
            book = doc.get("book", "Unknown")
            text = doc.get("content", "")[:100]
            print(f"  {i+1}. [{book}] {text}...")
        
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
