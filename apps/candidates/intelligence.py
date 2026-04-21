import logging
import httpx
from django.conf import settings
from apps.ai_service import gemini

logger = logging.getLogger("hirevox.intelligence")

def analyze_candidate_online_presence(candidate):
    """
    Main entry point to fetch and analyze GitHub and Portfolio.
    Updates the candidate.external_intelligence field.
    """
    intelligence = {}
    
    # 1. GitHub Analysis
    if candidate.github_url:
        try:
            github_data = _fetch_github_intelligence(candidate.github_url)
            intelligence["github"] = github_data
        except Exception as e:
            logger.error(f"GitHub analysis failed for {candidate.id}: {e}")

    # 2. Portfolio Analysis
    if candidate.portfolio_url:
        try:
            portfolio_data = _fetch_portfolio_intelligence(candidate.portfolio_url)
            intelligence["portfolio"] = portfolio_data
        except Exception as e:
            logger.error(f"Portfolio analysis failed for {candidate.id}: {e}")

    # 3. AI Overall Summary
    if intelligence:
        try:
            intelligence["overall_summary"] = _generate_combined_summary(candidate, intelligence)
            # Extract common tech stack
            intelligence["tech_stack"] = _extract_tech_stack(intelligence)
        except Exception as e:
            logger.error(f"AI summary failed for {candidate.id}: {e}")

    if intelligence:
        candidate.external_intelligence = intelligence
        candidate.save(update_fields=["external_intelligence", "updated_at"])

def _fetch_github_intelligence(url: str):
    # Extract username from url (https://github.com/username)
    username = url.strip("/").split("/")[-1]
    token = getattr(settings, "GITHUB_ACCESS_TOKEN", None)
    headers = {"Authorization": f"token {token}"} if token else {}
    
    with httpx.Client(headers=headers, timeout=10.0) as client:
        # Get user profile
        user_res = client.get(f"https://api.github.com/users/{username}")
        user_res.raise_for_status()
        user_data = user_res.json()
        
        # Get repos
        repos_res = client.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10")
        repos_res.raise_for_status()
        repos = repos_res.json()
        
    repo_summaries = [
        {
            "name": r["name"],
            "description": r["description"],
            "language": r["language"],
            "stars": r["stargazers_count"],
            "url": r["html_url"]
        } for r in repos if not r["fork"]
    ]
    
    # Let AI summarize the technical profile
    prompt = (
        f"Analyze this GitHub profile for a job application:\n"
        f"Bio: {user_data.get('bio')}\n"
        f"Public Repos: {len(repo_summaries)}\n"
        f"Featured Projects: {repo_summaries[:5]}\n\n"
        "Provide a 2-sentence technical summary of their expertise."
    )
    
    summary = gemini.generate_text(prompt, mode="fast")
    
    return {
        "username": username,
        "bio": user_data.get("bio"),
        "public_repos": user_data.get("public_repos"),
        "followers": user_data.get("followers"),
        "top_repositories": repo_summaries[:5],
        "ai_technical_summary": summary
    }

def _fetch_portfolio_intelligence(url: str):
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            res = client.get(url)
            res.raise_for_status()
            html = res.text[:10000] # Cap it
            
        prompt = (
            f"Analyze the content of this portfolio website: {url}\n"
            f"HTML Snippet: {html}\n\n"
            "Summarize the key projects and technologies mentioned. Keep it under 100 words."
        )
        summary = gemini.generate_text(prompt, mode="fast")
        return {"url": url, "summary": summary}
    except:
        return {"url": url, "summary": "Could not crawl portfolio site."}

def _generate_combined_summary(candidate, intelligence):
    prompt = (
        f"Summarize the online presence for candidate {candidate.name}.\n"
        f"GitHub Info: {intelligence.get('github')}\n"
        f"Portfolio Info: {intelligence.get('portfolio')}\n\n"
        "Provide a professional 'Instant Take' for a recruiter. Focus on strengths."
    )
    return gemini.generate_text(prompt, mode="reasoning")

def _extract_tech_stack(intelligence):
    # Just a simple extraction or we could use AI
    stack = []
    gh = intelligence.get("github", {})
    for r in gh.get("top_repositories", []):
        if r["language"] and r["language"] not in stack:
            stack.append(r["language"])
    return stack
