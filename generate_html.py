# generate_html_async.py
from requests_html import AsyncHTMLSession
import urllib.parse
import asyncio

async def fetch_html_and_js(url: str, render_js: bool = True, render_timeout: int = 30):
    """
    Async version using requests_html.AsyncHTMLSession safe to call from an async FastAPI endpoint.
    Returns dict: { html, javascript: {all, inline, external}, stats }
    """
    session = AsyncHTMLSession()
    try:
        resp = await session.get(url)
    except Exception as e:
        await session.close()
        return {"error": f"GET failed: {e}"}

    if render_js:
        try:
            # render is a coroutine on AsyncHTMLSession
            await resp.html.arender(timeout=render_timeout, sleep=2)  # arender for async
        except Exception as e:
            # render can fail on some sites; still continue with what we have
            # include debug info
            render_err = str(e)
        else:
            render_err = None
    else:
        render_err = None

    final_html = resp.html.html or ""
    inline_js = []
    external_js = []
    all_js = []

    for script in resp.html.find("script"):
        src = script.attrs.get("src")
        if not src:
            js_code = script.text or ""
            inline_js.append(js_code)
            all_js.append(js_code)
        else:
            script_url = urllib.parse.urljoin(url, src)
            try:
                js_resp = await session.get(script_url)
                js_code = js_resp.text or ""
                external_js.append(js_code)
                all_js.append(js_code)
            except Exception:
                # skip if can't download external script
                continue

    await session.close()

    return {
        "html": final_html.strip(),
        "javascript": {
            "all": all_js,
            "inline": inline_js,
            "external": external_js
        },
        "stats": {
            "html_length": len(final_html),
            "inline_js_count": len(inline_js),
            "external_js_count": len(external_js),
            "total_js_count": len(all_js)
        },
        "render_error": render_err
    }
