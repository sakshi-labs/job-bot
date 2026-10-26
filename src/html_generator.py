"""
HTML Resume Generator.
Renders an elegant, responsive, ATS-friendly HTML view suitable for browser preview
and printing.
"""
from .models import TailoredResume

def generate_html_resume(resume: TailoredResume, output_path: str) -> str:
    contacts = [
        f'<a href="mailto:{resume.email}">{resume.email}</a>',
        resume.phone,
        resume.location
    ]
    if resume.linkedin:
        contacts.append(f'<a href="{resume.linkedin}" target="_blank">LinkedIn</a>')
    if resume.github:
        contacts.append(f'<a href="{resume.github}" target="_blank">GitHub</a>')
    if resume.portfolio:
        contacts.append(f'<a href="{resume.portfolio}" target="_blank">Portfolio</a>')

    contact_bar = " &bull; ".join(contacts)

    skills_html = ""
    for cat, skills in resume.categorized_skills.items():
        if skills:
            skills_html += f"""
            <div class="skill-row">
                <span class="skill-cat">{cat}:</span>
                <span class="skill-list">{", ".join(skills)}</span>
            </div>
            """

    experiences_html = ""
    for exp in resume.experiences:
        bullets_li = "".join([f"<li>{b}</li>" for b in exp.bullets])
        experiences_html += f"""
        <div class="exp-item">
            <div class="exp-header">
                <div><strong>{exp.role}</strong> &mdash; <em>{exp.company}</em></div>
                <div class="exp-meta">{exp.start_date} &ndash; {exp.end_date} | {exp.location}</div>
            </div>
            <ul class="bullets">
                {bullets_li}
            </ul>
        </div>
        """

    projects_html = ""
    if resume.projects:
        proj_items = ""
        for p in resume.projects:
            tech = f" ({', '.join(p.get('technologies', []))})" if p.get("technologies") else ""
            proj_items += f"""
            <div class="proj-item">
                <div class="proj-title"><strong>{p.get('name')}</strong>{tech}</div>
                <div class="proj-desc">{p.get('description')}</div>
            </div>
            """
        projects_html = f"""
        <section class="sec">
            <h2>Key Projects</h2>
            <div class="sec-content">{proj_items}</div>
        </section>
        """

    education_html = ""
    if resume.education:
        edu_items = ""
        for edu in resume.education:
            highlights = f"<div class='edu-high'>Highlights: {edu.get('highlights')}</div>" if edu.get("highlights") else ""
            edu_items += f"""
            <div class="edu-item">
                <div class="edu-header">
                    <div><strong>{edu.get('degree')}</strong> &mdash; {edu.get('institution')}</div>
                    <div>{edu.get('graduation_date')}</div>
                </div>
                {highlights}
            </div>
            """
        education_html = f"""
        <section class="sec">
            <h2>Education</h2>
            <div class="sec-content">{edu_items}</div>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{resume.full_name} - Resume for {resume.target_role}</title>
<style>
    @page {{
        size: letter;
        margin: 0.5in;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #222;
        line-height: 1.45;
        max-width: 800px;
        margin: 20px auto;
        padding: 24px;
        background: #fff;
    }}
    .header {{
        text-align: center;
        border-bottom: 2px solid #2b4c7e;
        padding-bottom: 12px;
        margin-bottom: 16px;
    }}
    h1 {{
        margin: 0 0 6px 0;
        font-size: 26px;
        color: #1a2a3a;
        letter-spacing: 0.5px;
    }}
    .contacts {{
        font-size: 13px;
        color: #555;
    }}
    .contacts a {{
        color: #2b4c7e;
        text-decoration: none;
    }}
    h2 {{
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #2b4c7e;
        border-bottom: 1px solid #dcdcdc;
        margin: 16px 0 8px 0;
        padding-bottom: 3px;
    }}
    .summary {{
        font-size: 13.5px;
        color: #333;
        text-align: justify;
    }}
    .skill-row {{
        font-size: 13px;
        margin-bottom: 4px;
    }}
    .skill-cat {{
        font-weight: 600;
        color: #222;
    }}
    .skill-list {{
        color: #444;
    }}
    .exp-item {{
        margin-bottom: 12px;
    }}
    .exp-header {{
        display: flex;
        justify-content: space-between;
        font-size: 13.5px;
        margin-bottom: 3px;
    }}
    .exp-meta {{
        color: #666;
        font-size: 12.5px;
    }}
    .bullets {{
        margin: 4px 0 0 18px;
        padding: 0;
        font-size: 13px;
        color: #333;
    }}
    .bullets li {{
        margin-bottom: 3px;
    }}
    .proj-item, .edu-item {{
        margin-bottom: 8px;
        font-size: 13px;
    }}
    .edu-header {{
        display: flex;
        justify-content: space-between;
    }}
    .edu-high {{
        font-size: 12px;
        color: #555;
    }}
    @media print {{
        body {{
            margin: 0;
            padding: 0;
        }}
    }}
</style>
</head>
<body>
    <div class="header">
        <h1>{resume.full_name}</h1>
        <div class="contacts">{contact_bar}</div>
    </div>

    <section class="sec">
        <h2>Professional Summary</h2>
        <div class="summary">{resume.tailored_summary}</div>
    </section>

    <section class="sec">
        <h2>Technical Skills</h2>
        <div class="sec-content">{skills_html}</div>
    </section>

    <section class="sec">
        <h2>Professional Experience</h2>
        <div class="sec-content">{experiences_html}</div>
    </section>

    {projects_html}
    {education_html}
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
