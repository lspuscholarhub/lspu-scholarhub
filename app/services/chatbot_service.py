"""
AI Chatbot Service — LSPU ScholarHub
Powered by Google Gemini 1.5 Flash (free tier).

Features
--------
- Intent detection & entity extraction via Gemini
- Personalized responses using logged-in student's real data
- Live scholarship data injected into every request
- Multi-turn conversation with proper system prompt handling
- Contextual follow-up suggestions
- Graceful fallback to rule-based when API is unavailable
"""

import os
import json
import logging
from datetime import datetime
from app import db

logger = logging.getLogger(__name__)

# ── Gemini client (lazy singleton) ───────────────────────────────────────────

_genai   = None
_model   = None


def _init_gemini():
    """Initialise Gemini once and cache it. Returns (client, model_name) or (None, None)."""
    global _genai, _model
    if _model is not None:
        return _genai, _model

    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        logger.info('GEMINI_API_KEY not set — using rule-based fallback.')
        return None, None

    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=api_key)

        # Use model from env, fall back to probing candidates
        model_name = os.environ.get('GEMINI_MODEL', '').strip()
        if not model_name:
            for candidate in ['gemini-3-flash-preview', 'gemini-flash-latest', 'gemini-2.5-flash-lite']:
                try:
                    test = client.models.generate_content(model=candidate, contents='hi')
                    if test.text:
                        model_name = candidate
                        break
                except Exception:
                    continue

        if not model_name:
            logger.warning('No working Gemini model found — using rule-based fallback.')
            return None, None

        _genai  = client
        _model  = model_name
        logger.info(f'Gemini client initialised (model: {_model}).')
        return _genai, _model
    except Exception as e:
        logger.warning(f'Gemini init failed: {e}')
        return None, None


# ── Live context builders ─────────────────────────────────────────────────────

def _scholarship_context():
    """Return a structured text block of all currently open scholarships."""
    try:
        from app.models import Scholarship
        from app.models.scholarship import ScholarshipStatus

        scholarships = (Scholarship.query
                        .filter_by(status=ScholarshipStatus.ACTIVE)
                        .filter(
                            db.or_(
                                Scholarship.application_deadline > datetime.utcnow(),
                                Scholarship.application_deadline.is_(None)
                            )
                        )
                        .order_by(
                            db.case((Scholarship.application_deadline.is_(None), 1), else_=0),
                            Scholarship.application_deadline.asc()
                        )
                        .all())

        if not scholarships:
            return "There are currently NO open scholarships."

        lines = ["=== OPEN SCHOLARSHIPS (live from database) ==="]
        for s in scholarships:
            award    = f"₱{float(s.award_amount):,.2f}" if s.award_amount else "TBA"
            deadline = s.application_deadline.strftime('%B %d, %Y') if s.application_deadline else 'No deadline'
            days     = (s.application_deadline - datetime.utcnow()).days if s.application_deadline else None
            filled   = s.current_applicants or 0
            capacity = f"{filled}/{s.max_applicants}" if s.max_applicants else f"{filled} (no limit)"
            lines += [
                f"\n[{s.id}] {s.title}",
                f"  Award       : {award}",
                f"  Deadline    : {deadline}{f' ({days} days left)' if days is not None else ''}",
                f"  Slots       : {capacity}",
                f"  Eligibility : {s.eligibility_criteria}",
                f"  Benefits    : {s.benefits}",
                f"  Description : {s.description}",
            ]
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f'scholarship_context error: {e}')
        return "Scholarship data temporarily unavailable."


def _user_context(user_id):
    """Return personalised context for a logged-in student."""
    if not user_id:
        return ""
    try:
        from app.models import User, ScholarshipApplication
        from app.models.scholarship import ApplicationStatus

        user = User.query.get(user_id)
        if not user or user.user_type != 'student':
            return ""

        apps = user.applications or []
        pending  = [a for a in apps if a.status == ApplicationStatus.PENDING]
        review   = [a for a in apps if a.status == ApplicationStatus.UNDER_REVIEW]
        approved = [a for a in apps if a.status == ApplicationStatus.APPROVED]
        rejected = [a for a in apps if a.status == ApplicationStatus.REJECTED]

        lines = [
            "\n=== CURRENT USER (personalise your response to this student) ===",
            f"Name       : {user.get_full_name()}",
            f"Username   : {user.username}",
            f"Verified   : {'YES — can apply for scholarships' if user.is_verified else 'NO — account not yet verified (OTP is sent at registration)'}",
            f"Course     : {user.course or 'Not set'}",
            f"Year Level : {user.year_level or 'Not set'}",
            f"Student ID : {user.student_id or 'Not set'}",
            f"GWA        : {user.gwa if user.gwa else 'Not recorded'}",
            f"GWA Status : {'Current' if user.grades_up_to_date else 'Outdated or not uploaded'}",
            f"\nApplication Summary:",
            f"  Total     : {len(apps)}",
            f"  Pending   : {len(pending)} — {', '.join(a.scholarship.title for a in pending) or 'none'}",
            f"  Under Review: {len(review)} — {', '.join(a.scholarship.title for a in review) or 'none'}",
            f"  Approved  : {len(approved)} — {', '.join(a.scholarship.title for a in approved) or 'none'}",
            f"  Rejected  : {len(rejected)} — {', '.join(a.scholarship.title for a in rejected) or 'none'}",
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f'user_context error: {e}')
        return ""


def _build_system_prompt(user_id=None):
    """Assemble the full system prompt with live data."""
    scholarship_ctx = _scholarship_context()
    user_ctx        = _user_context(user_id)

    return f"""You are the official AI assistant for **LSPU ScholarHub** — the scholarship management system of Laguna State Polytechnic University (LSPU), Philippines.

## Your Persona
- Name: ScholarHub Assistant
- Tone: Friendly, warm, conversational, and genuinely helpful — like a knowledgeable friend who works at the scholarship office
- **LANGUAGE RULE — CRITICAL**: You MUST detect the language the user is writing in and respond in the SAME language.
  - If the user writes in Filipino/Tagalog → respond FULLY in Filipino/Tagalog
  - If the user writes in English → respond in English
  - If the user mixes English and Filipino → respond in the same mix
  - Examples: "pwede ba akong mag-apply?" → respond in Filipino. "Can I apply?" → respond in English.
- **Never make up information.** If unsure, direct the user to the scholarship office.
- **Base answers on THIS system.** Describe the process exactly as written in 'How LSPU ScholarHub Works' below — never generic scholarship advice from other schools or programs.

## How to Respond
- **Be concise and direct.** Answer the question first, then add only what's truly necessary.
- **Keep responses short.** 2–4 sentences for simple questions. Use bullet points only when listing multiple items.
- **Use the student's data.** If you already know their GWA, course, year level, or application status (see user context below), use it — don't ask them for information you already have.
- **Language rule**: Respond in the same language the user writes in. Filipino → Filipino. English → English. Mixed → mixed.
- **Never make up** scholarship amounts, deadlines, or eligibility criteria.
- **No filler.** Skip encouragement phrases, preambles, and "great question!" type openers. Just answer.
- Only ask a follow-up question if it is genuinely necessary to answer the user's question.

## System Information
- **University**: Laguna State Polytechnic University (LSPU), Sta. Cruz, Laguna, Philippines
- **Scholarship Office**: Student Affairs Building, 2nd Floor
- **Hours**: Monday–Friday, 8:00 AM – 5:00 PM
- **Email**: lspu.scholarhub@gmail.com
- **Phone**: 0968-365-2615

## How LSPU ScholarHub Works (describe THIS process — not generic scholarship advice)
1. **Register** — the student signs up with their school email and verifies via a One-Time PIN (OTP) sent by email. Verification is automatic after the OTP — no admin approval needed to apply.
2. **Upload documents once** — in **My Documents**, the student uploads their **Certificate of Registration (COR)** and **Copy of Grades**. The system reads the GWA from the grades automatically.
3. **Browse** — the **Scholarships** page lists open programs with award, deadline (if any), and remaining slots.
4. **Apply** — the form is pre-filled with the student's profile (name, course, year level, GWA, birthday, contact info). Each program may add its own **custom questions**. There is **no essay** and no document upload during application — COR and grades are already on file.5. **Public vs private scholarships** — a student may hold only **ONE public (government-funded)** scholarship at a time. **Private** scholarships are combinable — a student may hold several private programs, and private ones alongside their public scholarship.
6. **Review** — staff/admin approve or reject; the student is notified via in-app alert, email, and SMS (when configured).
7. **Auto-batching** — approved scholars are automatically placed in the batch named after their program for the current academic period.
8. **Monitoring** — each term, staff check every scholar's GWA: **Good Standing**, **At Risk**, **Probation**, **Termination Warning**. Students are alerted when their performance drops.

## Requirements (the ONLY ones in this system)
- **Account** — registered and OTP-verified.
- **Documents on file** — Certificate of Registration (COR) and Copy of Grades, uploaded in **My Documents** (PDF, JPG, or PNG; replaceable anytime).
- **Application form** — answer the program's custom questions only. **No essay is ever required.**
- **Eligibility** — the program must be open (active, before its deadline if set, slots remaining) and the student's GWA must satisfy the program's criteria.
- **Limit** — one active scholarship per student.

## Where things are in the system
- **Scholarships** — browse programs and apply
- **My Applications** — track status; edit or withdraw pending applications
- **My Documents** — upload or replace COR and Copy of Grades
- **Notifications** — in-app alerts of every status change

## Application Status Meanings
- **Pending** — Received, waiting for review
- **Under Review** — Staff is currently reviewing it
- **Approved** — Congratulations! Application was approved
- **Rejected** — Not approved this time; student may apply to other scholarships
- **Withdrawn** — Student withdrew the application

## NLP Instructions
- Detect the user's **intent** and answer it directly
- Extract **entities** from the message (scholarship names, GWA values, course, year level)
- If the user mentions their GWA, course, or year level — use that to recommend specific scholarships from the live data and explain why they qualify
- If the user seems worried or stressed, be reassuring in one sentence, then answer

{scholarship_ctx}

{user_ctx}

## Critical Rules
1. Only mention scholarships that appear in the live data above
2. Never invent award amounts, deadlines, or eligibility criteria
3. If a scholarship the user asks about is NOT in the list, say it may not be currently open
4. Always use the student's first name if they are logged in (see user context above)
5. If the student is NOT verified, tell them briefly — one sentence only
6. **Never ask for information you already have** — if you know their GWA, course, year level, or application status from the user context, USE IT instead of asking
7. Keep responses short and direct — no padding, no unnecessary tips, no lengthy encouragement
"""


# ── Intent detection ──────────────────────────────────────────────────────────

def _detect_intent(text):
    """
    Quick local intent detection to pre-classify the message.
    Used to enrich the prompt and for analytics.
    """
    t = text.lower()
    if any(w in t for w in ['available', 'open', 'list', 'what scholarship', 'show scholarship', 'mga scholarship']):
        return 'list_scholarships'
    if any(w in t for w in ['deadline', 'due date', 'last day', 'kelan', 'when is']):
        return 'deadline_inquiry'
    if any(w in t for w in ['eligib', 'qualify', 'who can', 'pwede', 'requirement']):
        return 'eligibility_inquiry'
    if any(w in t for w in ['how to apply', 'paano mag-apply', 'apply', 'mag-apply']):
        return 'application_process'
    if any(w in t for w in ['document', 'upload', 'file', 'copy of grades', 'certificate of registration', 'transcript', 'good moral']):
        return 'document_inquiry'
    if any(w in t for w in ['status', 'check', 'approved', 'rejected', 'pending', 'under review']):
        return 'status_inquiry'
    if any(w in t for w in ['verify', 'verified', 'verification', 'otp', 'one-time', 'account']):
        return 'verification_inquiry'
    if any(w in t for w in ['contact', 'office', 'phone', 'email', 'address', 'location']):
        return 'contact_inquiry'
    if any(w in t for w in ['benefit', 'how much', 'amount', 'award', 'pera', 'money']):
        return 'benefits_inquiry'
    if any(w in t for w in ['hello', 'hi', 'good morning', 'good afternoon', 'kumusta']):
        return 'greeting'
    return 'general'


# ── Rule-based fallback ───────────────────────────────────────────────────────

def _rule_based_response(user_message, user_id=None):
    """Keyword-based fallback with live DB data when Gemini is unavailable."""
    from app.models import Scholarship
    from app.models.scholarship import ScholarshipStatus

    intent = _detect_intent(user_message)

    # Greeting
    if intent == 'greeting':
        name = ""
        if user_id:
            try:
                from app.models import User
                u = User.query.get(user_id)
                if u:
                    name = f", {u.first_name}"
            except Exception:
                pass
        return (f"Hello{name}! I'm your LSPU ScholarHub assistant. "
                "I can help with scholarships, applications, eligibility, deadlines, "
                "and more. What would you like to know?")

    # List scholarships
    if intent == 'list_scholarships':
        try:
            scholarships = (Scholarship.query
                            .filter_by(status=ScholarshipStatus.ACTIVE)
                            .filter(
                                db.or_(
                                    Scholarship.application_deadline > datetime.utcnow(),
                                    Scholarship.application_deadline.is_(None)
                                )
                            ).all())
            if not scholarships:
                return "There are currently no open scholarships. Please check back later or visit the Scholarships page."
            lines = []
            for i, s in enumerate(scholarships, 1):
                award = f"₱{float(s.award_amount):,.0f}" if s.award_amount else "TBA"
                days  = (s.application_deadline - datetime.utcnow()).days if s.application_deadline else None
                suffix = f" | {days} days left" if days is not None else ''
                lines.append(f"{i}. **{s.title}** — {award}{suffix}")
            return "**Currently open scholarships:**\n" + "\n".join(lines) + "\n\nVisit the Scholarships page to view details and apply."
        except Exception:
            pass

    # Deadlines
    if intent == 'deadline_inquiry':
        try:
            scholarships = (Scholarship.query
                            .filter_by(status=ScholarshipStatus.ACTIVE)
                            .filter(
                                db.or_(
                                    Scholarship.application_deadline > datetime.utcnow(),
                                    Scholarship.application_deadline.is_(None)
                                )
                            ).all())
            if scholarships:
                lines = []
                for s in scholarships:
                    if s.application_deadline:
                        lines.append(f"• **{s.title}**: {s.application_deadline.strftime('%B %d, %Y')} ({(s.application_deadline - datetime.utcnow()).days} days left)")
                    else:
                        lines.append(f"• **{s.title}**: No deadline set")
                return "**Application deadlines:**\n" + "\n".join(lines) + "\n\nMake sure to submit before the deadline!"
        except Exception:
            pass

    # Benefits / amounts
    if intent == 'benefits_inquiry':
        try:
            scholarships = (Scholarship.query
                            .filter_by(status=ScholarshipStatus.ACTIVE)
                            .filter(
                                db.or_(
                                    Scholarship.application_deadline > datetime.utcnow(),
                                    Scholarship.application_deadline.is_(None)
                                )
                            ).all())
            if scholarships:
                lines = [f"• **{s.title}**: ₱{float(s.award_amount):,.0f}" if s.award_amount
                         else f"• **{s.title}**: TBA"
                         for s in scholarships]
                return "**Award amounts for open scholarships:**\n" + "\n".join(lines)
        except Exception:
            pass

    # Application process
    if intent == 'application_process':
        return ("**How to apply:**\n"
                "1. Register and verify via the OTP sent to your email\n"
                "2. Upload your **COR** and **Copy of Grades** once in **My Documents**\n"
                "3. Open the **Scholarships** page and pick an open program\n"
                "4. Click **Apply** — your profile is pre-filled; just answer the program's custom questions\n"
                "5. Submit and track it in **My Applications**\n\n"                "No essay needed. You may hold only one PUBLIC scholarship at a time, but private scholarships can be combined with it and with each other.")

    # Documents
    if intent == 'document_inquiry':
        return ("**Required documents (upload once in My Documents):**\n"
                "- Certificate of Registration (COR)\n"
                "- Copy of Grades — your GWA is read from this automatically\n\n"
                "Formats: PDF, JPG, or PNG. Replace them anytime to update your records. "
                "No essay or other files are required.")

    # Status
    if intent == 'status_inquiry':
        return ("Track your applications under **My Applications** in the navbar.\n\n"
                "Statuses: **Pending** (awaiting review) → **Under Review** → **Approved** or **Rejected**. "
                "You can edit or withdraw while pending. You'll get in-app, email, and SMS "
                "notifications on every change.")

    # Verification
    if intent == 'verification_inquiry':
        return ("Accounts are verified automatically with a **One-Time PIN (OTP)** sent to "
                "your email when you register. Didn't get it? Use the resend option, or "
                "contact the office at **lspu.scholarhub@gmail.com** / 0968-365-2615.")

    # Eligibility
    if intent == 'eligibility_inquiry':
        try:
            scholarships = (Scholarship.query
                            .filter_by(status=ScholarshipStatus.ACTIVE)
                            .filter(
                                db.or_(
                                    Scholarship.application_deadline > datetime.utcnow(),
                                    Scholarship.application_deadline.is_(None)
                                )
                            ).all())
            if scholarships:
                lines = [f"• **{s.title}**: {s.eligibility_criteria[:100]}{'…' if len(s.eligibility_criteria) > 100 else ''}"
                         for s in scholarships]
                return "**Eligibility criteria:**\n" + "\n".join(lines) + "\n\nCheck each scholarship's details page for full requirements."
        except Exception:
            pass

    # Contact
    if intent == 'contact_inquiry':
        return ("**Scholarship Office Contact:**\n"
                "- 📍 Student Affairs Building, 2nd Floor, LSPU Sta. Cruz Campus\n"
                "- 📧 lspu.scholarhub@gmail.com\n"
                "- 📞 0968-365-2615\n"
                "- 🕐 Monday–Friday, 8:00 AM – 5:00 PM")

    return ("I can help with: available scholarships, how to apply, eligibility, "
            "deadlines, required documents, application status, and account verification.\n\n"
            "What would you like to know?")


# ── Suggested follow-ups ──────────────────────────────────────────────────────

_FOLLOWUPS = {
    'list_scholarships':    ["What are the eligibility requirements?", "How do I apply?", "What documents do I need?"],
    'deadline_inquiry':     ["How do I apply?", "What documents do I need?", "What are the eligibility requirements?"],
    'eligibility_inquiry':  ["What scholarships are available?", "How do I apply?", "What documents do I need?"],
    'application_process':  ["What documents do I need?", "How do I check my application status?", "Where is the scholarship office?"],
    'document_inquiry':     ["How do I apply?", "What scholarships are available?", "How do I check my application status?"],
    'status_inquiry':       ["What scholarships are available?", "How do I apply?", "Where is the scholarship office?"],
    'verification_inquiry': ["What scholarships are available?", "How do I apply?", "Where is the scholarship office?"],
    'benefits_inquiry':     ["What are the eligibility requirements?", "How do I apply?", "What is the application deadline?"],
    'contact_inquiry':      ["What scholarships are available?", "How do I apply?", "What documents do I need?"],
    'greeting':             ["What scholarships are available?", "How do I apply?", "What documents do I need?"],
    'general':              ["What scholarships are available?", "How do I apply?", "What are the eligibility requirements?"],
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_chatbot_response(user_message, conversation_history=None, user_id=None):
    """
    Main entry point.

    Parameters
    ----------
    user_message         : str   — the user's latest message
    conversation_history : list  — [{role: 'user'|'model', content: str}, ...]
    user_id              : int   — logged-in user's ID for personalisation (optional)

    Returns
    -------
    dict: response, source, category, intent, suggestions
    """
    if not user_message or not user_message.strip():
        return {
            'response':    ("Hello! I'm the LSPU ScholarHub AI assistant. "
                            "Ask me about scholarships, applications, eligibility, "
                            "deadlines, or documents. How can I help you?"),
            'source':      'fallback',
            'category':    'greeting',
            'intent':      'greeting',
            'suggestions': _FOLLOWUPS['greeting'],
        }

    intent = _detect_intent(user_message)
    client, model_name = _init_gemini()

    # ── Gemini AI path ────────────────────────────────────────────────────────
    if client and model_name:
        try:
            from google.genai import types as genai_types

            system_prompt = _build_system_prompt(user_id)

            # Build chat history for context
            contents = []

            # Inject system context as first user/model exchange
            contents.append(genai_types.Content(
                role='user',
                parts=[genai_types.Part(text=system_prompt)]
            ))
            contents.append(genai_types.Content(
                role='model',
                parts=[genai_types.Part(text=(
                    "Understood. I am the LSPU ScholarHub AI assistant. "
                    "I will answer only scholarship-related questions using the live data provided. "
                    "I will always respond in the same language the user writes in — "
                    "Filipino if they write in Filipino, English if they write in English."
                ))]
            ))

            # Add conversation history (last 6 turns)
            if conversation_history:
                for turn in conversation_history[-6:]:
                    role    = turn.get('role', 'user')
                    content = turn.get('content', '')
                    if role in ('user', 'model') and content:
                        contents.append(genai_types.Content(
                            role=role,
                            parts=[genai_types.Part(text=content)]
                        ))

            # Add the current message
            contents.append(genai_types.Content(
                role='user',
                parts=[genai_types.Part(text=user_message)]
            ))

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    temperature=0.5,
                    top_p=0.95,
                    max_output_tokens=1024,
                )
            )
            text = response.text.strip()

            # Ask Gemini for contextual follow-up suggestions
            suggestions = _FOLLOWUPS.get(intent, _FOLLOWUPS['general'])
            try:
                sugg_contents = contents + [
                    genai_types.Content(role='model', parts=[genai_types.Part(text=text)]),
                    genai_types.Content(role='user', parts=[genai_types.Part(text=(
                        "Based on this conversation, suggest exactly 3 short follow-up questions "
                        "the user might want to ask next. Return ONLY a JSON array of 3 strings, "
                        "nothing else. Example: [\"Question 1?\", \"Question 2?\", \"Question 3?\"]"
                    ))])
                ]
                sugg_response = client.models.generate_content(
                    model=model_name,
                    contents=sugg_contents,
                    config=genai_types.GenerateContentConfig(temperature=0.3, max_output_tokens=200)
                )
                raw   = sugg_response.text.strip()
                start = raw.find('[')
                end   = raw.rfind(']') + 1
                if start != -1 and end > start:
                    parsed = json.loads(raw[start:end])
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        suggestions = [str(s) for s in parsed[:3]]
            except Exception:
                pass

            return {
                'response':    text,
                'source':      'gemini',
                'category':    'ai',
                'intent':      intent,
                'suggestions': suggestions,
            }

        except Exception as e:
            logger.warning(f'Gemini error ({type(e).__name__}): {e}')

    # ── Rule-based fallback ───────────────────────────────────────────────────
    response_text = _rule_based_response(user_message, user_id)
    return {
        'response':    response_text,
        'source':      'fallback',
        'category':    'help',
        'intent':      intent,
        'suggestions': _FOLLOWUPS.get(intent, _FOLLOWUPS['general']),
    }
