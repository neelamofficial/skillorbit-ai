
import os
import re
import json
import sqlite3
from pathlib import Path

import streamlit as st
import pandas as pd

# Optional PDF support
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# Optional OpenAI support
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="SkillOrbit AI",
    page_icon="🪐",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = Path("skillorbit.db")


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        education TEXT,
        degree TEXT,
        semester TEXT,
        interests TEXT,
        experience TEXT,
        projects TEXT,
        cv_text TEXT,
        target_career TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS careers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        skills TEXT,
        interests TEXT
    );

    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        organization TEXT,
        type TEXT,
        field TEXT,
        skills TEXT,
        location TEXT,
        url TEXT
    );

    CREATE TABLE IF NOT EXISTS roadmaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        career TEXT,
        roadmap TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def seed_database():
    conn = get_connection()
    cur = conn.cursor()

    careers = [
        (
            "Data Analyst",
            "Analyze data to find patterns, insights, and support better decisions.",
            "Excel,SQL,Python,Statistics,Data Visualization,Communication",
            "Data,Technology,Research,Business,Analytics"
        ),
        (
            "UX Researcher",
            "Study users and their behavior to improve digital products and experiences.",
            "Research,User Interviews,Communication,Usability Testing,Data Analysis,Empathy",
            "Psychology,Research,Design,Technology,Human Behavior"
        ),
        (
            "Research Assistant",
            "Support academic or industry research through data collection, analysis, and reporting.",
            "Research,Academic Writing,Statistics,Data Analysis,Communication,SPSS",
            "Research,Psychology,Education,Science,Social Science"
        ),
        (
            "HR Analyst",
            "Use people data and business information to improve hiring and workforce decisions.",
            "Excel,Data Analysis,Communication,HR,Reporting,Research",
            "Psychology,Business,People,Management,Data"
        ),
        (
            "Digital Marketer",
            "Plan and analyze digital marketing campaigns and audience engagement.",
            "Marketing,Content Writing,Social Media,Analytics,Communication,SEO",
            "Marketing,Creativity,Business,Communication,Technology"
        ),
        (
            "Software Developer",
            "Design, build, test, and maintain software applications.",
            "Programming,Problem Solving,Git,Algorithms,Databases,Communication",
            "Technology,Programming,Software,Problem Solving"
        ),
        (
            "AI / Machine Learning Engineer",
            "Build intelligent systems using data, machine learning, and AI techniques.",
            "Python,Statistics,Machine Learning,Data Analysis,SQL,Git",
            "AI,Technology,Data,Programming,Mathematics"
        ),
        (
            "Product Manager",
            "Coordinate product strategy, user needs, business goals, and development teams.",
            "Communication,Research,Leadership,Product Strategy,Data Analysis,Problem Solving",
            "Business,Technology,Leadership,Research,People"
        ),
        (
            "Graphic Designer",
            "Create visual communication for brands, products, campaigns, and digital media.",
            "Graphic Design,Typography,Branding,Visual Communication,Creativity,UI Design",
            "Design,Creativity,Art,Marketing,Media"
        ),
        (
            "Content Strategist",
            "Plan and optimize useful content for audiences, brands, and digital products.",
            "Writing,Content Strategy,Research,SEO,Communication,Analytics",
            "Writing,Marketing,Creativity,Research,Media"
        ),
    ]

    for career in careers:
        cur.execute("""
            INSERT OR IGNORE INTO careers
            (name, description, skills, interests)
            VALUES (?, ?, ?, ?)
        """, career)

    opportunities = [
        ("Research Internship", "University / Research Lab", "Internship", "Research", "Research,Statistics,Writing,Communication", "Remote", ""),
        ("Data Analytics Internship", "Technology Company", "Internship", "Data", "Excel,SQL,Python,Data Analysis", "Remote", ""),
        ("UX Research Internship", "Digital Product Company", "Internship", "UX", "Research,Communication,User Interviews", "Remote", ""),
        ("HR Internship", "Corporate Organization", "Internship", "HR", "Communication,Excel,Research,HR", "Pakistan", ""),
        ("Digital Marketing Internship", "Marketing Agency", "Internship", "Marketing", "Marketing,SEO,Content,Analytics", "Remote", ""),
        ("Python for Data Analysis", "Online Learning Platform", "Course", "Data", "Python,Pandas,Data Analysis", "Online", ""),
        ("SQL Fundamentals", "Online Learning Platform", "Course", "Data", "SQL,Databases", "Online", ""),
        ("UX Research Fundamentals", "Online Learning Platform", "Course", "UX", "Research,User Interviews,Usability Testing", "Online", ""),
        ("Research Methods Course", "Online Learning Platform", "Course", "Research", "Research,Statistics,Academic Writing", "Online", ""),
        ("Portfolio Project Challenge", "SkillOrbit", "Project", "General", "Projects,Communication,Problem Solving", "Online", ""),
    ]

    for opp in opportunities:
        cur.execute("""
            INSERT OR IGNORE INTO opportunities
            (title, organization, type, field, skills, location, url)
            SELECT ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM opportunities
                WHERE title = ? AND organization = ?
            )
        """, opp + (opp[0], opp[1]))

    conn.commit()
    conn.close()


init_db()
seed_database()


# ============================================================
# HELPERS
# ============================================================

def normalize_list(text):
    if not text:
        return []
    parts = re.split(r"[,;\n|]+", str(text))
    return [p.strip() for p in parts if p.strip()]


def normalize_skill(skill):
    return re.sub(r"[^a-z0-9+# ]", "", skill.lower()).strip()


def get_careers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM careers ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_opportunities():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM opportunities ORDER BY type, title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def extract_pdf_text(uploaded_file):
    if PyPDF2 is None:
        return ""
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()
    except Exception:
        return ""


def extract_cv_text(uploaded_file):
    if uploaded_file is None:
        return ""

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".pdf"):
        return extract_pdf_text(uploaded_file)

    if file_name.endswith(".txt"):
        try:
            return uploaded_file.getvalue().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    return ""


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def ai_generate(prompt, system_message="You are a helpful student career advisor."):
    client = get_openai_client()

    if client is None:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return f"AI service error: {exc}"


def build_student_profile():
    return {
        "name": st.session_state.get("name", ""),
        "education": st.session_state.get("education", ""),
        "degree": st.session_state.get("degree", ""),
        "semester": st.session_state.get("semester", ""),
        "skills": st.session_state.get("skills", []),
        "interests": st.session_state.get("interests", []),
        "experience": st.session_state.get("experience", ""),
        "projects": st.session_state.get("projects", ""),
        "cv_text": st.session_state.get("cv_text", ""),
        "target_career": st.session_state.get("target_career", ""),
    }


def score_career(profile, career):
    student_skills = {normalize_skill(x) for x in profile["skills"]}
    student_interests = {normalize_skill(x) for x in profile["interests"]}

    required_skills = normalize_list(career["skills"])
    career_interests = normalize_list(career["interests"])

    skill_scores = []
    matched_skills = []

    for skill in required_skills:
        ns = normalize_skill(skill)
        found = any(
            ns == ss or ns in ss or ss in ns
            for ss in student_skills
        )
        if found:
            skill_scores.append(1)
            matched_skills.append(skill)
        else:
            skill_scores.append(0)

    interest_scores = []
    matched_interests = []

    for interest in career_interests:
        ni = normalize_skill(interest)
        found = any(
            ni == si or ni in si or si in ni
            for si in student_interests
        )
        if found:
            interest_scores.append(1)
            matched_interests.append(interest)
        else:
            interest_scores.append(0)

    skill_ratio = sum(skill_scores) / len(skill_scores) if skill_scores else 0
    interest_ratio = sum(interest_scores) / len(interest_scores) if interest_scores else 0

    degree_text = f"{profile['degree']} {profile['education']} {profile['cv_text']}".lower()
    career_text = f"{career['name']} {career['description']} {career['interests']}".lower()

    education_bonus = 0.1 if any(
        word and word in career_text and word in degree_text
        for word in ["psychology", "business", "computer", "technology", "design",
                     "research", "marketing", "science", "education", "data"]
    ) else 0

    score = min(100, round((skill_ratio * 60) + (interest_ratio * 30) + (education_bonus * 100)))

    return {
        "career": career["name"],
        "description": career["description"],
        "score": score,
        "matched_skills": matched_skills,
        "missing_skills": [x for x in required_skills if x not in matched_skills],
        "matched_interests": matched_interests,
        "required_skills": required_skills,
    }


def recommend_careers(profile):
    results = [score_career(profile, career) for career in get_careers()]
    return sorted(results, key=lambda x: x["score"], reverse=True)


def generate_roadmap(career_result, profile):
    missing = career_result["missing_skills"]

    if not missing:
        missing = ["Portfolio Project", "Interview Preparation"]

    roadmap = []
    for i, skill in enumerate(missing[:6], start=1):
        roadmap.append({
            "phase": i,
            "skill": skill,
            "action": f"Learn the fundamentals of {skill}, practice it, and create one small project demonstrating it."
        })

    return roadmap


def opportunity_matches(profile, career_name="", limit=8):
    opportunities = get_opportunities()
    profile_skills = {normalize_skill(x) for x in profile["skills"]}
    interests = {normalize_skill(x) for x in profile["interests"]}

    scored = []

    for opp in opportunities:
        required = normalize_list(opp["skills"])
        field = normalize_skill(opp["field"])

        skill_matches = sum(
            1 for skill in required
            if any(
                normalize_skill(skill) == s
                or normalize_skill(skill) in s
                or s in normalize_skill(skill)
                for s in profile_skills
            )
        )

        interest_match = any(
            field in i or i in field for i in interests
        ) if field else False

        career_match = career_name and (
            normalize_skill(career_name.split()[0]) in normalize_skill(opp["field"])
            or normalize_skill(opp["field"]) in normalize_skill(career_name)
        )

        score = skill_matches * 3 + int(interest_match) * 2 + int(bool(career_match)) * 3
        scored.append((score, opp))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:limit]]


def save_student(profile):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO students
        (name, education, degree, semester, interests, experience, projects,
         cv_text, target_career)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        profile["name"],
        profile["education"],
        profile["degree"],
        profile["semester"],
        ", ".join(profile["interests"]),
        profile["experience"],
        profile["projects"],
        profile["cv_text"],
        profile["target_career"],
    ))

    student_id = cur.lastrowid
    conn.commit()
    conn.close()
    return student_id


def save_roadmap(student_id, career, roadmap):
    conn = get_connection()
    conn.execute(
        "INSERT INTO roadmaps (student_id, career, roadmap) VALUES (?, ?, ?)",
        (student_id, career, json.dumps(roadmap)),
    )
    conn.commit()
    conn.close()


# ============================================================
# STYLING
# ============================================================

st.markdown("""
<style>
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0;
    }

    .subtitle {
        font-size: 1.15rem;
        opacity: 0.75;
        margin-bottom: 1.5rem;
    }

    .card {
        padding: 1.2rem;
        border-radius: 16px;
        border: 1px solid rgba(128,128,128,0.25);
        margin-bottom: 1rem;
    }

    .score {
        font-size: 2rem;
        font-weight: 800;
    }

    .tag {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        border: 1px solid rgba(128,128,128,0.3);
        margin: 0.15rem;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "name": "",
    "education": "",
    "degree": "",
    "semester": "",
    "skills": [],
    "interests": [],
    "experience": "",
    "projects": "",
    "cv_text": "",
    "cv_name": "",
    "target_career": "",
    "recommendations": [],
    "selected_career": None,
    "roadmap": [],
    "opportunities": [],
    "student_id": None,
    "chat_history": [],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 🪐 SkillOrbit AI")
    st.caption("Where Skills Meet Opportunity")

    page = st.radio(
        "Navigate",
        [
            "🏠 Home",
            "👤 My Profile",
            "🎯 Career Matches",
            "🧩 Skill Gap",
            "🗺️ Learning Roadmap",
            "💼 Opportunities",
            "🤖 Career AI",
        ],
    )

    st.divider()

    if st.session_state["name"]:
        st.success(f"Profile: {st.session_state['name']}")
    else:
        st.info("Create your profile to unlock personalized recommendations.")

    if os.getenv("OPENAI_API_KEY"):
        st.caption("🟢 AI connected")
    else:
        st.caption("🟡 AI key not configured")


# ============================================================
# HOME
# ============================================================

if page == "🏠 Home":
    st.markdown('<div class="main-title">🪐 SkillOrbit AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Where Skills Meet Opportunity — discover your career direction, '
        'find your skill gaps, and turn them into an actionable roadmap.</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state["name"]:
        st.info("Start by creating your student profile from the sidebar.")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("🎯 Career Paths", len(get_careers()))

    with c2:
        st.metric("🧠 Skill Analysis", "AI")

    with c3:
        st.metric("💼 Opportunities", len(get_opportunities()))

    with c4:
        st.metric("🤖 Career Chat", "24/7")

    st.divider()

    st.subheader("How SkillOrbit works")

    steps = [
        ("1", "Build Profile", "Tell SkillOrbit about your education, skills, interests, projects, and experience."),
        ("2", "Analyze", "Upload your CV and let the system understand your current profile."),
        ("3", "Discover", "Get potential career paths with an explanation of why they match you."),
        ("4", "Find Gaps", "See which skills you already have and which ones you need to develop."),
        ("5", "Take Action", "Get a personalized learning roadmap and matching opportunities."),
        ("6", "Ask AI", "Chat with your personalized career advisor using your profile as context."),
    ]

    cols = st.columns(3)
    for i, (num, title, desc) in enumerate(steps):
        with cols[i % 3]:
            st.markdown(
                f'<div class="card"><h3>{num}. {title}</h3><p>{desc}</p></div>',
                unsafe_allow_html=True,
            )

    st.subheader("The SkillOrbit idea")

    st.write(
        "Most students know where they are studying, but they are not always sure where "
        "their skills can take them. SkillOrbit connects the student's current profile "
        "to possible careers, identifies the missing skills, and turns those gaps into "
        "a practical path forward."
    )


# ============================================================
# PROFILE
# ============================================================

elif page == "👤 My Profile":
    st.title("👤 Build Your Career Profile")
    st.caption("The better your profile, the more personalized your recommendations will be.")

    with st.form("profile_form"):
        name = st.text_input("Full Name", value=st.session_state["name"])

        col1, col2 = st.columns(2)
        with col1:
            education = st.text_input(
                "Education",
                value=st.session_state["education"],
                placeholder="e.g. Bachelor's"
            )
            degree = st.text_input(
                "Degree / Field",
                value=st.session_state["degree"],
                placeholder="e.g. BS Psychology"
            )

        with col2:
            semester = st.text_input(
                "Semester / Year",
                value=st.session_state["semester"],
                placeholder="e.g. 5th Semester"
            )

        skills_text = st.text_input(
            "Your Skills",
            value=", ".join(st.session_state["skills"]),
            placeholder="e.g. Research, Communication, Excel, SPSS"
        )

        interests_text = st.text_input(
            "Your Interests",
            value=", ".join(st.session_state["interests"]),
            placeholder="e.g. Psychology, Research, Technology"
        )

        experience = st.text_area(
            "Experience",
            value=st.session_state["experience"],
            placeholder="Internships, volunteering, part-time work, leadership, etc."
        )

        projects = st.text_area(
            "Projects",
            value=st.session_state["projects"],
            placeholder="Academic or personal projects you have completed."
        )

        uploaded_cv = st.file_uploader(
            "Upload CV / Resume (PDF or TXT)",
            type=["pdf", "txt"]
        )

        submitted = st.form_submit_button(
            "🚀 Analyze My Profile",
            use_container_width=True
        )

    if submitted:
        st.session_state["name"] = name.strip()
        st.session_state["education"] = education.strip()
        st.session_state["degree"] = degree.strip()
        st.session_state["semester"] = semester.strip()
        st.session_state["skills"] = normalize_list(skills_text)
        st.session_state["interests"] = normalize_list(interests_text)
        st.session_state["experience"] = experience.strip()
        st.session_state["projects"] = projects.strip()

        if uploaded_cv:
            cv_text = extract_cv_text(uploaded_cv)
            st.session_state["cv_name"] = uploaded_cv.name
            st.session_state["cv_text"] = cv_text

            if not cv_text:
                st.warning(
                    "The CV was uploaded, but no readable text was extracted. "
                    "Scanned/image-only PDFs may need OCR."
                )

        profile = build_student_profile()

        if not profile["name"] or not profile["degree"]:
            st.error("Please provide at least your name and degree/field.")
        else:
            st.session_state["recommendations"] = recommend_careers(profile)
            student_id = save_student(profile)
            st.session_state["student_id"] = student_id

            if st.session_state["recommendations"]:
                st.session_state["selected_career"] = st.session_state["recommendations"][0]
                st.session_state["target_career"] = st.session_state["recommendations"][0]["career"]

            st.success("Profile analyzed successfully. Open Career Matches to see your results.")

    if st.session_state["cv_name"]:
        st.caption(f"Uploaded CV: {st.session_state['cv_name']}")

    if st.session_state["cv_text"]:
        with st.expander("View extracted CV text"):
            st.text(st.session_state["cv_text"][:8000])


# ============================================================
# CAREER MATCHES
# ============================================================

elif page == "🎯 Career Matches":
    st.title("🎯 Your Potential Career Paths")

    if not st.session_state["recommendations"]:
        st.warning("Create your profile first.")
        st.stop()

    st.write(
        "These are potential matches based on your current information. "
        "They are recommendations, not fixed career decisions."
    )

    recommendations = st.session_state["recommendations"]

    for rank, result in enumerate(recommendations[:5], start=1):
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])

            with col1:
                st.subheader(f"{rank}. {result['career']}")
                st.write(result["description"])

                if result["matched_skills"]:
                    st.markdown(
                        "**Matching skills:** "
                        + " • ".join(result["matched_skills"])
                    )

                if result["missing_skills"]:
                    st.markdown(
                        "**Skills to develop:** "
                        + " • ".join(result["missing_skills"][:5])
                    )

            with col2:
                st.metric("Profile Match", f"{result['score']}%")

            if st.button(
                f"Explore {result['career']}",
                key=f"explore_{rank}",
                use_container_width=True,
            ):
                st.session_state["selected_career"] = result
                st.session_state["target_career"] = result["career"]
                st.session_state["roadmap"] = generate_roadmap(
                    result, build_student_profile()
                )
                st.session_state["opportunities"] = opportunity_matches(
                    build_student_profile(), result["career"]
                )
                st.success(f"{result['career']} selected.")


# ============================================================
# SKILL GAP
# ============================================================

elif page == "🧩 Skill Gap":
    st.title("🧩 Skill Gap Analysis")

    result = st.session_state.get("selected_career")

    if not result:
        st.warning("Go to Career Matches and select a career first.")
        st.stop()

    st.subheader(result["career"])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ✅ Skills You Already Have")
        if result["matched_skills"]:
            for skill in result["matched_skills"]:
                st.success(skill)
        else:
            st.info("No direct skill matches found yet.")

    with col2:
        st.markdown("### 📌 Skills To Develop")
        if result["missing_skills"]:
            for skill in result["missing_skills"]:
                st.warning(skill)
        else:
            st.success("Your listed skills cover the current career requirements.")

    st.divider()

    st.subheader("What this means")

    if result["missing_skills"]:
        st.write(
            f"You already have a foundation for **{result['career']}**, but the system "
            "found some skills that could strengthen your profile. These gaps are "
            "used to build your learning roadmap."
        )
    else:
        st.write(
            "Your current profile covers the main skills in our starter career database. "
            "The next step should be building projects and gaining real experience."
        )


# ============================================================
# ROADMAP
# ============================================================

elif page == "🗺️ Learning Roadmap":
    st.title("🗺️ Your Personalized Learning Roadmap")

    result = st.session_state.get("selected_career")

    if not result:
        st.warning("Select a career first.")
        st.stop()

    if not st.session_state["roadmap"]:
        st.session_state["roadmap"] = generate_roadmap(
            result, build_student_profile()
        )

    st.subheader(f"Goal: {result['career']}")

    st.progress(0.15, text="Starting your career journey")

    roadmap = st.session_state["roadmap"]

    for item in roadmap:
        with st.container(border=True):
            st.markdown(f"### Phase {item['phase']} — {item['skill']}")
            st.write(item["action"])

    st.divider()

    st.subheader("🚀 Career Action Plan")

    action_items = [
        "Complete the first skill in your roadmap.",
        "Build one small project related to your target career.",
        "Add the project and relevant skills to your CV.",
        "Apply to at least one matching opportunity.",
        "Use Career AI to ask questions about your next step.",
    ]

    for item in action_items:
        st.checkbox(item, key=f"action_{item[:12]}")


# ============================================================
# OPPORTUNITIES
# ============================================================

elif page == "💼 Opportunities":
    st.title("💼 Opportunities For You")

    profile = build_student_profile()

    if not profile["name"]:
        st.warning("Create your profile first.")
        st.stop()

    career_name = st.session_state.get("target_career", "")
    opportunities = opportunity_matches(profile, career_name)

    if not opportunities:
        st.info("No matching opportunities found in the current demo database.")
        st.stop()

    st.caption(
        "The hackathon MVP uses a curated local opportunity database. "
        "For production, this can be connected to live opportunity APIs or approved data sources."
    )

    for opp in opportunities:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])

            with c1:
                st.subheader(opp["title"])
                st.write(f"**Organization:** {opp['organization']}")
                st.write(f"**Type:** {opp['type']}  |  **Field:** {opp['field']}")
                st.write(f"**Location:** {opp['location']}")
                st.write(f"**Relevant skills:** {opp['skills']}")

            with c2:
                if opp["url"]:
                    st.link_button("View Opportunity", opp["url"])
                else:
                    st.caption("Demo opportunity")


# ============================================================
# AI CHATBOT
# ============================================================

elif page == "🤖 Career AI":
    st.title("🤖 Career AI")
    st.caption("Ask questions about your career, skills, CV, roadmap, or opportunities.")

    profile = build_student_profile()

    if not profile["name"]:
        st.warning("Create your profile first.")
        st.stop()

    if not st.session_state["chat_history"]:
        st.session_state["chat_history"] = [
            {
                "role": "assistant",
                "content": (
                    f"Hi {profile['name']}! I’m your SkillOrbit Career AI. "
                    "Ask me about your career options, skill gaps, roadmap, CV, "
                    "or what you should do next."
                ),
            }
        ]

    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_message = st.chat_input(
        "Ask something like: What should I learn next?"
    )

    if user_message:
        st.session_state["chat_history"].append(
            {"role": "user", "content": user_message}
        )

        recommendations = st.session_state.get("recommendations", [])
        top_careers = ", ".join(
            [r["career"] for r in recommendations[:3]]
        )

        selected = st.session_state.get("selected_career")
        skill_gaps = ", ".join(
            selected["missing_skills"] if selected else []
        )

        roadmap_text = json.dumps(
            st.session_state.get("roadmap", []),
            ensure_ascii=False
        )

        context = f"""
Student name: {profile['name']}
Education: {profile['education']}
Degree: {profile['degree']}
Semester: {profile['semester']}
Skills: {', '.join(profile['skills'])}
Interests: {', '.join(profile['interests'])}
Experience: {profile['experience']}
Projects: {profile['projects']}
Target career: {profile['target_career']}
Top potential careers: {top_careers}
Current skill gaps: {skill_gaps}
Current roadmap: {roadmap_text}
CV text: {profile['cv_text'][:5000]}
"""

        prompt = f"""
You are SkillOrbit AI, a personalized student career advisor.

Use the student's profile below to answer the question.

STUDENT PROFILE:
{context}

QUESTION:
{user_message}

Rules:
- Give practical, student-friendly advice.
- Do not claim that a career recommendation is guaranteed.
- Use the student's actual profile when possible.
- If recommending a skill, explain why it matters.
- If recommending a next step, make it actionable.
- Do not invent specific jobs, deadlines, salaries, organizations, or links.
- If information is missing, clearly say what is missing.
"""

        with st.chat_message("assistant"):
            with st.spinner("SkillOrbit is thinking..."):
                ai_response = ai_generate(prompt)

                if ai_response is None:
                    # Useful fallback when no API key is configured.
                    if "next" in user_message.lower():
                        if selected and selected["missing_skills"]:
                            ai_response = (
                                f"Based on your current profile, your next priority "
                                f"should be **{selected['missing_skills'][0]}** because "
                                f"it is one of the main skills missing for "
                                f"**{selected['career']}**. After learning it, build a "
                                "small project so you can demonstrate the skill."
                            )
                        else:
                            ai_response = (
                                "Your next step should be to select a target career, "
                                "identify its required skills, and build one project "
                                "that demonstrates those skills."
                            )
                    else:
                        ai_response = (
                            "AI chat is not connected yet. Add an OPENAI_API_KEY "
                            "in your Streamlit deployment secrets to enable the "
                            "personalized AI advisor."
                        )

                st.write(ai_response)

        st.session_state["chat_history"].append(
            {"role": "assistant", "content": ai_response}
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption("🪐 SkillOrbit AI — Where Skills Meet Opportunity")
