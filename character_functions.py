# character_functions.py
import json
import numpy as np
from typing import Dict, List, Optional
import os


from config import COLOR_KEYS
from models import LLMGeneratedQuestions, Users, Marriage

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

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0.0 or nb == 0.0: return 0.0
    return float(np.dot(a, b) / (na * nb))

def calculate_character_similarity(b, g, y, r):
    # 🚨 FIX: Convert all inputs to numbers
    try:
        b = float(b) if b is not None else 0.0
        g = float(g) if g is not None else 0.0
        y = float(y) if y is not None else 0.0
        r = float(r) if r is not None else 0.0
    except (ValueError, TypeError) as e:
        print(f"❌ Error converting character scores to numbers: {e}")
        b, g, y, r = 0.0, 0.0, 0.0, 0.0
    
    total = b + g + y + r
    
    if total <= 0:
        return 0.0
    
    # Normalize the values
    b_norm = b / total
    g_norm = g / total
    y_norm = y / total
    r_norm = r / total
    
    # Ideal distribution (you can adjust these weights based on your preference)
    ideal_b = 0.4  # 40% blue (stable/calm)
    ideal_g = 0.3  # 30% green (growth-oriented)  
    ideal_y = 0.2  # 20% yellow (cautious)
    ideal_r = 0.1  # 10% red (passionate)
    
    # Calculate similarity using cosine similarity or simple difference
    # Using simple weighted difference for now
    similarity = 1.0 - (
        abs(b_norm - ideal_b) * 0.25 +
        abs(g_norm - ideal_g) * 0.25 +
        abs(y_norm - ideal_y) * 0.25 +
        abs(r_norm - ideal_r) * 0.25
    )
    
    # Ensure score is between 0 and 1
    return max(0.0, min(1.0, similarity))

def get_user_background(user_id: int) -> Dict:
    """Get comprehensive user background for LLM analysis"""
    background = {}

    # Get basic user info
    user = Users.query.filter_by(user_id=user_id).first()
    if user:
        background.update({
            "name": user.name or "Unknown",
            "email": user.email or "",
        })

    # Get marriage profile if exists
    marriage_profile = Marriage.query.filter_by(user_id=user_id).first()
    if marriage_profile:
        background.update({
            "current_location": marriage_profile.current_city or "",
            "education": marriage_profile.education_level or "",
            "employment": marriage_profile.employment_status or "",
            "hobbies": marriage_profile.hobbies_interests or "",
            "conflict_style": marriage_profile.conflict_approach or "",
            "financial_style": marriage_profile.financial_style or "",
            "family_type": marriage_profile.family_type or "",
        })

    return background

def generate_character_llm_explanation(u_vec, v_vec):
    """Character explanation using FAISS + LLM - NO FALLBACK"""
    
    print("🟢 Starting LLM character explanation...")
    
    if not HAS_LLM:
        raise Exception("LLM service is currently unavailable. Please try again later.")
    
    # Import inside function to avoid circular imports
    try:
        from faiss_service import get_faiss_context
        context = get_faiss_context(3)
    except ImportError:
        context = ""

    data = {
        "User1": [float(u_vec[0]), float(u_vec[1]), float(u_vec[2]), float(u_vec[3])],
        "User2": [float(v_vec[0]), float(v_vec[1]), float(v_vec[2]), float(v_vec[3])]
    }

    json_data = json.dumps(data, indent=2)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
    You are a personality and relationship compatibility expert.

    Generate CHARACTER compatibility in EXACTLY 3 groups with these EXACT section headers:

    1. Character Strengths
    2. Character Risks  
    3. Sacrifices Needed

    CRITICAL RULES:
    - Use ONLY these exact section headers: "Character Strengths", "Character Risks", "Sacrifices Needed"
    - NO markdown formatting
    - Each section should have 1-5 points based on actual needs
    - Write only the points that are truly necessary
    - If only one point is needed, write only one point
    - If no points are needed in a section, write "None" for that section
    - Maximum 5 points per section for very low compatibility cases
    - Each point should be a complete sentence starting with a capital letter
    - Separate sections with a blank line
    - No color names, no trait labels, no percentages
    - Use simple English that anyone can understand
    - Don't use "User1" or "User2" - refer to them as "the two people" or "both persons"
    - BE TRUTHFUL: Write only real strengths, risks, and sacrifices based on their actual compatibility
    """),
        ("human", """
    ### PERSONALITY DATA
    {json_data}

    ### BOOK CONTEXT
    {context}

    Generate the character analysis in the exact format specified above.
    Write only the points that are truly needed - no filler content.
    Use simple language that everyone can understand.
    """)
    ])

    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.65,
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=60,
            max_retries=2,
            request_timeout=60
        )
        
        chain = prompt | llm | StrOutputParser()

        print("⏳ Generating AI-powered character analysis...")
        res = chain.invoke({"json_data": json_data, "context": context})
        
        print(f"🔍 DEBUG: Raw LLM response = {res}")
        
        if not res or len(res.strip()) < 10:
            raise Exception("AI analysis returned insufficient response")
        
        # Process the response into lines
        lines = []
        for line in res.split('\n'):
            line = line.strip()
            if line and not line.startswith('###'):  # Remove markdown headers
                lines.append(line)
        
        # Ensure we have all three sections
        if len(lines) < 3:  # At least headers for all three sections
            print(f"⚠️ LLM returned insufficient lines: {len(lines)}")
            # Fallback: use the original response but clean it up
            lines = [line for line in res.split('\n') if line.strip() and not line.startswith('###')]
            
        print(f"✅ AI character analysis completed with {len(lines)} lines")
        return lines[:15]  # Increased limit for flexible points
        
    except Exception as e:
        print(f"🔴 LLM character explanation failed: {e}")
        raise Exception(f"AI analysis failed: {str(e)}. Please try again.")

def generate_character_fallback_explanation(u_vec, v_vec):
    """Generate structured fallback explanation when LLM is unavailable"""
    
    # Calculate basic similarity
    character_score = cosine_sim(u_vec, v_vec)
    
    # Analyze dominant colors from vectors
    colors = ['Blue', 'Green', 'Yellow', 'Red']
    u_dominant_idx = np.argmax(u_vec)
    v_dominant_idx = np.argmax(v_vec)
    
    dominant_color_u = colors[u_dominant_idx]
    dominant_color_v = colors[v_dominant_idx]
    
    # Generate sections based on color combinations
    strengths = generate_fallback_strengths(dominant_color_u, dominant_color_v)
    risks = generate_fallback_risks(dominant_color_u, dominant_color_v)
    sacrifices = generate_fallback_sacrifices(dominant_color_u, dominant_color_v)
    
    # Build explanation in LLM-like format
    explanation = []
    explanation.append(f"Character Score: {round(character_score * 100, 1)}%")
    explanation.append("")
    explanation.append("Character Strengths")
    explanation.extend([f"• {s}" for s in strengths])
    explanation.append("")
    explanation.append("Character Risks")
    explanation.extend([f"• {r}" for r in risks])
    explanation.append("")
    explanation.append("Sacrifices Needed From Both Partners")
    explanation.extend([f"• {s}" for s in sacrifices])
    
    return explanation

def generate_fallback_strengths(color1, color2):
    """Generate strengths based on color combination"""
    combinations = {
        ('Blue', 'Red'): [
            "Analytical thinking complements decisive action",
            "Thorough planning balances quick decision-making", 
            "Data-driven approach supports confident leadership"
        ],
        ('Green', 'Yellow'): [
            "Structured organization grounds creative ideas",
            "Process-oriented approach gives vision practical form",
            "Reliability provides stability for innovation"
        ],
        ('Blue', 'Green'): [
            "Detailed analysis combines with systematic execution",
            "Methodical approach ensures thorough implementation",
            "Precision and organization create reliable outcomes"
        ],
        ('Red', 'Yellow'): [
            "Action-oriented drive brings creative ideas to life",
            "Bold decisions support visionary thinking",
            "Energy and enthusiasm fuel innovative projects"
        ],
        ('Blue', 'Yellow'): [
            "Analytical depth enhances creative problem-solving",
            "Thorough research supports innovative approaches",
            "Logical thinking balances imaginative ideas"
        ],
        ('Green', 'Red'): [
            "Organized planning directs decisive action",
            "Systematic approach channels energetic drive",
            "Process efficiency supports quick implementation"
        ]
    }
    
    key = tuple(sorted([color1, color2]))
    return combinations.get(key, [
        "Complementary personality traits create balance",
        "Different approaches bring diverse perspectives", 
        "Varied strengths cover multiple relationship aspects"
    ])

def generate_fallback_risks(color1, color2):
    """Generate risks based on color combination"""
    combinations = {
        ('Blue', 'Red'): [
            "Over-analysis may frustrate action-oriented partner",
            "Quick decisions might overlook important details",
            "Direct communication may clash with thoughtful processing"
        ],
        ('Green', 'Yellow'): [
            "Rigid routines may limit spontaneous creativity", 
            "Unstructured ideas may disrupt organized systems",
            "Process focus might slow down innovative thinking"
        ],
        ('Blue', 'Green'): [
            "Excessive planning may delay actual progress",
            "Over-caution might prevent necessary risks",
            "Analysis paralysis in decision-making situations"
        ],
        ('Red', 'Yellow'): [
            "Impulsive actions may lack long-term vision",
            "Big ideas might overlook practical implementation",
            "Enthusiasm may override careful consideration"
        ],
        ('Blue', 'Yellow'): [
            "Over-thinking may dampen spontaneous creativity",
            "Abstract ideas might lack practical grounding",
            "Detail focus could miss the bigger picture"
        ],
        ('Green', 'Red'): [
            "Bureaucratic processes may frustrate quick action",
            "Impulsive decisions could disrupt careful planning",
            "Directness may overwhelm methodical approach"
        ]
    }
    
    key = tuple(sorted([color1, color2]))
    return combinations.get(key, [
        "Different communication styles may cause misunderstandings",
        "Varying energy levels could lead to timing conflicts",
        "Contrasting approaches to problems may create tension"
    ])

def generate_fallback_sacrifices(color1, color2):
    """Generate sacrifices based on color combination"""
    combinations = {
        ('Blue', 'Red'): [
            "Analytical partner must accept quicker decisions sometimes",
            "Action-oriented partner needs to allow time for reflection", 
            "Both must find middle ground between speed and thoroughness"
        ],
        ('Green', 'Yellow'): [
            "Organized partner should embrace some spontaneity",
            "Creative partner needs to respect established routines",
            "Both must balance structure with flexibility"
        ],
        ('Blue', 'Green'): [
            "Need to move from planning to action more quickly",
            "Must embrace some uncertainty in decision-making",
            "Both should practice more direct communication"
        ],
        ('Red', 'Yellow'): [
            "Need to ground big ideas with practical steps",
            "Must balance enthusiasm with realistic planning",
            "Both should develop more patience in execution"
        ],
        ('Blue', 'Yellow'): [
            "Analytical thinker should embrace intuitive leaps",
            "Creative partner needs to consider practical constraints",
            "Both must balance imagination with reality checks"
        ],
        ('Green', 'Red'): [
            "Structured partner should allow faster execution sometimes",
            "Action-oriented partner needs to follow established processes",
            "Both must compromise between speed and quality"
        ]
    }
    
    key = tuple(sorted([color1, color2]))
    return combinations.get(key, [
        "Both partners need to understand different communication styles",
        "Compromise between individual preferences and shared needs",
        "Balance personal approaches with relationship harmony"
    ])

def detailed_explanation(user1_id: int, user2_id: int, u_vec: np.ndarray, v_vec: np.ndarray) -> List[str]:
    """Main function to generate detailed explanations"""
    return generate_dynamic_explanation(user1_id, user2_id, u_vec, v_vec)

def generate_dynamic_explanation(user1_id: int, user2_id: int, user1_vec: np.ndarray, user2_vec: np.ndarray) -> List[str]:
    """Generate dynamic explanation using LLM and knowledge base"""
    
    # Get user backgrounds
    user1_bg = get_user_background(user1_id)
    user2_bg = get_user_background(user2_id)

    # Create query for knowledge base
    query = f"compatibility between personality types: {user1_bg.get('conflict_style', '')} and {user2_bg.get('conflict_style', '')}"
    
    # Import knowledge inside the function to avoid circular import
    try:
        from faiss_service import knowledge
        context_chunks = knowledge.get_relevant_context(query, topk=2) if knowledge else []
    except ImportError:
        context_chunks = []
    
    context = "\n".join(context_chunks) if context_chunks else "No specific psychological context available."
    # Try LLM first if available
    if HAS_LLM and os.getenv("OPENAI_API_KEY"):
        try:
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.7,
                max_retries=2,
                timeout=30
            )

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """You are a relationship compatibility expert specializing in personality color analysis (Blue, Green, Yellow, Red).
                Based on the personality profiles, relevant psychological context, and user profiles, provide a detailed compatibility analysis.

                CRITICAL GUIDELINES:
                1. Focus on practical relationship dynamics, not just theoretical compatibility
                2. Use insights from the provided psychological context when relevant
                3. Be specific about strengths and potential challenges
                4. Provide actionable advice for the couple
                5. Keep explanations natural and conversational, not robotic
                6. Reference specific personality traits and how they interact
                7. Consider cultural and personal background when relevant
                8. Balance positivity with realistic expectations

                Structure your response with:
                - Compatibility overview (1-2 sentences)
                - Key strengths of this pairing
                - Potential challenges to be aware of
                - Practical advice for success
                - Daily life compatibility"""),
                ("human", """Personality Profiles:
User 1 ({user1_name}, {user1_gender}): Blue {user1_blue}%, Green {user1_green}%, Yellow {user1_yellow}%, Red {user1_red}%
User 2 ({user2_name}, {user2_gender}): Blue {user2_blue}%, Green {user2_green}%, Yellow {user2_yellow}%, Red {user2_red}%

User 1 Background: {user1_background}
User 2 Background: {user2_background}

Relevant Psychological Context:
{context}

Please provide a comprehensive compatibility analysis:""")
            ])

            chain = prompt_template | llm | StrOutputParser()
            
            response = chain.invoke({
                "user1_name": user1_bg.get("name", "User 1"),
                "user1_gender": user1_bg.get("gender", "Not specified"),
                "user1_blue": round(user1_vec[0] * 100, 1),
                "user1_green": round(user1_vec[1] * 100, 1),
                "user1_yellow": round(user1_vec[2] * 100, 1),
                "user1_red": round(user1_vec[3] * 100, 1),
                "user2_name": user2_bg.get("name", "User 2"),
                "user2_gender": user2_bg.get("gender", "Not specified"),
                "user2_blue": round(user2_vec[0] * 100, 1),
                "user2_green": round(user2_vec[1] * 100, 1),
                "user2_yellow": round(user2_vec[2] * 100, 1),
                "user2_red": round(user2_vec[3] * 100, 1),
                "user1_background": json.dumps(user1_bg, indent=2),
                "user2_background": json.dumps(user2_bg, indent=2),
                "context": context
            })
            
            # Parse LLM response into structured points
            points = []
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('- Compatibility', '- Key', '- Potential', '- Practical', '- Daily')):
                    if line.startswith('Ã¢â‚¬Â¢') or line.startswith('-'):
                        points.append(line[1:].strip())
                    elif len(line) > 20:  # Substantive lines
                        points.append(line)

            if points:
                return points[:5]  # Return top 5 most relevant points
        except Exception as e:
            print(f"LLM explanation failed: {e}")

    # Fallback to rule-based explanations
    return generate_rule_based_explanation(user1_vec, user2_vec, user1_bg, user2_bg)

def generate_rule_based_explanation(user1_vec: np.ndarray, user2_vec: np.ndarray, user1_bg: Dict, user2_bg: Dict) -> List[str]:
    """Rule-based fallback explanation"""
    labels = ["Blue", "Green", "Yellow", "Red"]
    user1_dom = labels[int(np.argmax(user1_vec))]
    user2_dom = labels[int(np.argmax(user2_vec))]

    explanations = []

    # Dominant trait analysis
    if user1_dom == user2_dom:
        explanations.append(f"Both share {user1_dom} dominance: Strong alignment in core approach and values.")
    else:
        explanations.append(f"{user1_dom}-{user2_dom} pairing: Complementary strengths create balanced dynamics.")

    # Difference analysis
    diffs = user2_vec - user1_vec
    for idx, diff in enumerate(diffs):
        color = labels[idx]
        if abs(diff) > 0.15:
            if diff > 0:
                explanations.append(f"Higher {color} influence brings {get_color_strength(color)} to the relationship.")
            else:
                explanations.append(f"Lower {color} presence allows for more {get_color_balance(color)} in dynamics.")

    # Background considerations
    if user1_bg.get("hobbies") and user2_bg.get("hobbies"):
        explanations.append("Shared interests and hobbies create strong bonding opportunities.")

    if user1_bg.get("conflict_style") and user2_bg.get("conflict_style"):
        explanations.append("Complementary conflict styles can lead to effective problem-solving.")

    return explanations[:4]  # Limit to 4 points

def get_color_strength(color: str) -> str:
    strengths = {
        "Blue": "analytical precision and structured thinking",
        "Green": "emotional stability and patient understanding",
        "Yellow": "creative energy and social connection",
        "Red": "decisive action and goal orientation"
    }
    return strengths.get(color, "unique strengths")

def get_color_balance(color: str) -> str:
    balances = {
        "Blue": "flexibility and spontaneity",
        "Green": "directness and assertiveness",
        "Yellow": "focus and routine",
        "Red": "collaboration and patience"
    }
    return balances.get(color, "balanced approaches")