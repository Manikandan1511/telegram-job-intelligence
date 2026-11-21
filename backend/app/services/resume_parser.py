import json
import re

SECTION_NAMES={
    "education":"education",
    "academic background":"education",
    "experience":"experience",
    "work experience":"experience",
    "professional experience":"experience",
    "projects":"projects",
    "personal projects":"projects",
    "certifications":"certifications",
    "certificates":"certifications",
}

def parse_resume(text:str)->dict:
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    sections={"education":[],"experience":[],"projects":[],"certifications":[]}
    current=None
    for line in lines:
        heading=re.sub(r"[:\s]+$","",line.lower())
        if heading in SECTION_NAMES:
            current=SECTION_NAMES[heading]
            continue
        if current and len(line)<120:
            sections[current].append(line)
    first=next((line for line in lines[:8] if "@" not in line and not re.search(r"https?://|resume|curriculum vitae",line,re.I) and len(line)<=100),None)
    email=re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",text,re.I)
    degree=re.search(r"\b(B\.?\s?Tech|M\.?\s?Tech|B\.?\s?E\.?|M\.?\s?E\.?|BCA|MCA|BSc|MSc|B\.Com|M\.Com|Bachelor(?:'s)?(?:\s+of\s+[A-Za-z ]+)?|Master(?:'s)?(?:\s+of\s+[A-Za-z ]+)?)\b",text,re.I)
    cgpa=re.search(r"\b(?:CGPA|GPA)\s*[:\-]?\s*(\d+(?:\.\d+)?(?:\s*/\s*\d+)?)",text,re.I)
    graduation=re.search(r"(?:graduat(?:ion|e)|pass.?out|batch|expected)\D{0,24}(20\d{2})",text,re.I)
    college=next((line[:300] for line in lines if re.search(r"\b(university|college|institute of technology)\b",line,re.I)),None)
    return {
        "name":first,"email":email.group(0) if email else None,
        "degree":degree.group(0).strip() if degree else None,
        "college":college,"cgpa":cgpa.group(1) if cgpa else None,
        "graduation_year":int(graduation.group(1)) if graduation else None,
        "education":"\n".join(sections["education"]) or None,
        "experience_json":json.dumps(sections["experience"]),
        "projects_json":json.dumps(sections["projects"]),
        "certifications_json":json.dumps(sections["certifications"]),
    }
