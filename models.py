# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Users(db.Model):
    __tablename__ = "Users"
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128))
    password = db.Column(db.String(128))
    created_at = db.Column(db.DateTime)

class LLMGeneratedQuestions(db.Model):
    __tablename__ = "LLMGeneratedQuestions"

    llm_id     = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, nullable=False, index=True)
    role       = db.Column(db.String(64), nullable=True)
    blue       = db.Column(db.Integer, nullable=False, default=0)
    green      = db.Column(db.Integer, nullable=False, default=0)
    yellow     = db.Column(db.Integer, nullable=False, default=0)
    red        = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def color_vec(self):
        import numpy as np
        v = np.array([self.blue, self.green, self.yellow, self.red], dtype=np.float32)
        s = float(v.sum())
        return v / s if s > 0 else v

class Marriage(db.Model):
    __tablename__ = "Marriage"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    full_name = db.Column(db.String(100))
    date_of_birth = db.Column(db.String(50))
    gender = db.Column(db.String(20))
    current_city = db.Column(db.String(100))
    marital_status = db.Column(db.String(50))
    education_level = db.Column(db.String(100))
    employment_status = db.Column(db.String(100))
    number_of_siblings = db.Column(db.String(50))
    family_type = db.Column(db.String(100))
    hobbies_interests = db.Column(db.Text)
    conflict_approach = db.Column(db.String(100))
    financial_style = db.Column(db.String(100))
    income_range = db.Column(db.String(100))
    relocation_willingness = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    height = db.Column(db.String(100))  # Changed from height_weight
    skin_tone = db.Column(db.String(50))
    languages_spoken = db.Column(db.String(200))
    country = db.Column(db.String(100))
    blood_group = db.Column(db.String(10))
    religion = db.Column(db.String(100))
    dual_citizenship = db.Column(db.String(50))
    siblings_position = db.Column(db.String(50))
    parents_living_status = db.Column(db.String(100))
    live_with_parents = db.Column(db.String(50))
    support_parents_financially = db.Column(db.String(50))
    family_communication_frequency = db.Column(db.String(100))
    food_preference = db.Column(db.String(100))
    smoking_habit = db.Column(db.String(50))
    alcohol_habit = db.Column(db.String(50))
    daily_routine = db.Column(db.String(200))
    fitness_level = db.Column(db.String(100))
    own_pets = db.Column(db.String(50))
    travel_preference = db.Column(db.String(100))
    relaxation_mode = db.Column(db.String(100))
    job_role = db.Column(db.String(100))
    work_experience_years = db.Column(db.String(50))
    career_aspirations = db.Column(db.String(200))
    field_of_study = db.Column(db.String(200))
    remark = db.Column(db.Text)
    # 🚨 NEW FIELDS
    children_timeline = db.Column(db.String(100))
    open_to_adoption = db.Column(db.String(50))
    deal_breakers = db.Column(db.Text)
    other_non_negotiables = db.Column(db.Text)
    health_constraints = db.Column(db.String(200))
    live_with_inlaws = db.Column(db.String(50))

class ExpectationResponse(db.Model):
    __tablename__ = "ExpectationResponse"

    user_id = db.Column(db.Integer, primary_key=True)
    pref_age_range = db.Column(db.String(100))
    pref_height_range = db.Column(db.String(100))
    pref_current_city = db.Column(db.String(100))
    pref_countries = db.Column(db.String(100))
    pref_languages = db.Column(db.String(100))
    health_constraints = db.Column(db.String(200))
    pref_diet = db.Column(db.String(100))
    accept_smoking = db.Column(db.String(50))
    accept_alcohol = db.Column(db.String(50))
    pref_fitness = db.Column(db.String(100))
    pref_family_type = db.Column(db.String(100))
    live_with_inlaws = db.Column(db.String(50))  # 🚨 CHANGED: Remove 'pref_' prefix
    children_timeline = db.Column(db.String(100))
    open_to_adoption = db.Column(db.String(50))
    pref_conflict_approach = db.Column(db.String(100))
    pref_financial_style = db.Column(db.String(100))
    religion_alignment = db.Column(db.String(50))
    pref_shared_hobbies = db.Column(db.String(200))
    travel_pref = db.Column(db.String(100))
    pet_pref = db.Column(db.String(50))
    pref_income_range = db.Column(db.String(100))
    deal_breakers = db.Column(db.Text)
    other_non_negotiables = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pref_education_level = db.Column(db.String(100))
    pref_employment_status = db.Column(db.String(100))
    expectation_summary = db.Column(db.Text)
    _mandatory_fields = db.Column(db.Text)
    skin_tone = db.Column(db.String(50))
    marital_status = db.Column(db.String(50))
    daily_routine = db.Column(db.String(200))
    family_communication_frequency = db.Column(db.String(100))
    relaxation_mode = db.Column(db.String(100))
    pref_partner_relocation = db.Column(db.String(50))
    financial_support_to_parents = db.Column(db.String(50))
    pref_career_aspirations = db.Column(db.String(200))
    pref_live_with_parents = db.Column(db.String(50))