"""Portal sessions: visits to the HCP portal by generated prescribers, anonymous visitors and bots."""

from datetime import datetime, timedelta

from population.core import AS_OF, STATES, Entity, register
from population import engagement as eng
from population.entities.hcp_emails import START

SITE = "quorvantahcp.example"
PAGES = {
    "home": {"title": "QUORVANTA for healthcare professionals", "content": [], "gated": False},
    "isi": {"title": "Important Safety Information", "content": ["PROMO-ISI"], "gated": False},
    "efficacy": {"title": "Clinical data", "content": ["PROMO-DETAIL-AID"], "gated": True},
    "dosing": {"title": "Dosing and monitoring", "content": ["PROMO-DOSING-CARD"], "gated": True},
    "safety": {"title": "Safety profile", "content": ["PROMO-DETAIL-AID", "PROMO-ISI"], "gated": True},
    "access": {"title": "Prescribing and access", "content": ["access/how-to-prescribe.md"], "gated": False},
    "start-form": {"title": "QUORVANTA Start Form (download)", "content": ["access/start-form.md"], "gated": False},
    "request-medinfo": {"title": "Ask Medical Information", "content": [], "gated": True},
    "request-rep": {"title": "Request a representative", "content": [], "gated": True},
}
BOT_PAGES = 15          # a session with at least this many page views, each under 2 seconds, is automated


@register
class PortalSessions(Entity):
    name = "portal-sessions"
    id_prefix = "PPRT"
    default_count = 1
    count_means = "(not used)"
    requires = ("hcps", "hcp-emails")
    references = {"hcp_id": "hcps", "email_id": "hcp-emails", "quality_flags[].of": "portal-sessions"}
    notice = f"FICTITIOUS. Generated visits to an HCP portal ({SITE}) for a product that does not exist."
    usage = (f"One record per session on the HCP portal between {START} and the as_of date. hcp_id is set when a "
             "registered prescriber is signed in and null for anonymous visitors. source is email (with email_id, starting "
             "within 60 seconds of a human click in hcp-emails.json), rep_link, search or direct. region is the state the "
             "connection comes from. page_views give each page's id from the pages catalog in this header, its offset "
             "from the session start and the seconds spent on it. Gated pages need a signed-in, verified prescriber. "
             "quality_flags mark sessions that should not count as engagement or that a portal should have refused.")
    flags = {
        "bot_session": f"Automated traffic: {BOT_PAGES} or more page views, each under 2 seconds.",
        "shared_login": "The same prescriber signed in from two regions at overlapping times; 'of' is the other session.",
        "inactive_prescriber_login": "Signed in as a prescriber who is retired or whose NPI was deactivated before the session.",
        "gated_page_unverified": "A gated page viewed in an anonymous session.",
    }
    header = {"site": SITE, "pages": PAGES}

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        hcps = ctx.records("hcps")
        by_id = {h["id"]: h for h in hcps}
        states = list(STATES)
        days = (AS_OF - START).days
        out = []

        def views(pages, human=True):
            t, v = 0, []
            for pg in pages:
                sec = rng.randrange(8, 240) if human else rng.randrange(0, 2)
                v.append({"page": pg, "offset": t, "seconds": sec})
                t += sec + (rng.randrange(1, 6) if human else 0)
            return v

        def browse(first, gated_ok):
            open_pages = [p for p, d in PAGES.items() if gated_ok or not d["gated"]]
            pages = [first] + [rng.choice(open_pages) for _ in range(rng.randrange(0, 5))]
            return [p for i, p in enumerate(pages) if i == 0 or p != pages[i - 1]]

        def session(hcp, start, source, email_id, region, first, flags=()):
            rec = {"id": None, "hcp_id": hcp["id"] if hcp else None, "started_at": eng.iso(start), "source": source,
                   "email_id": email_id, "region": region, "page_views": views(browse(first, hcp is not None)),
                   "quality_flags": [{"type": f} for f in flags]}
            out.append(rec)
            return rec

        def when():
            d = START + timedelta(days=rng.randrange(days))
            return eng.at_local(d, rng.randrange(7, 22), rng.randrange(60), "NY")

        # Sessions that follow a human click in an approved email.
        for e in ctx.records("hcp-emails"):
            for ev in e["events"]:
                if ev["type"] == "clicked" and not ev["machine"] and rng.random() < 0.85:
                    h = by_id[e["hcp_id"]]
                    t = datetime.fromisoformat(ev["at"].replace("Z", "+00:00")) + timedelta(seconds=rng.randrange(1, 50))
                    if eng.local_date(t, h["state"]) <= AS_OF and h["status"] == "active":
                        session(h, t, "email", e["id"], h["state"], ev["page"])
        # Registered prescribers visiting on their own or from a representative's link.
        active = [h for h in hcps if h["status"] == "active" and not h["quality_flags"]]
        for h in rng.sample(active, len(active) // 3):
            for _ in range(rng.randrange(1, 4)):
                session(h, when(), rng.choice(["direct", "search", "rep_link"]), None, h["state"],
                        rng.choice(["home", "dosing", "efficacy", "access"]))
        # Anonymous visitors see only open pages.
        for _ in range(len(active) // 2):
            session(None, when(), rng.choice(["direct", "search"]), None, rng.choice(states), rng.choice(["home", "isi", "access", "start-form"]))

        # Data problems a portal analytics pipeline should catch.
        for _ in range(3):
            rec = session(None, when(), "direct", None, rng.choice(states), "home", ["bot_session"])
            rec["page_views"] = views([rng.choice(list(PAGES)) for _ in range(rng.randrange(BOT_PAGES, 40))], human=False)
            if any(PAGES[v["page"]]["gated"] for v in rec["page_views"]):
                rec["quality_flags"].append({"type": "gated_page_unverified"})
        a = rng.choice([s for s in out if s["hcp_id"] and s["source"] != "email" and not s["quality_flags"]])
        start = datetime.fromisoformat(a["started_at"].replace("Z", "+00:00")) + timedelta(seconds=rng.randrange(30, 200))
        other_region = rng.choice([s for s in states if s != a["region"]])
        b = session(by_id[a["hcp_id"]], start, "direct", None, other_region, "efficacy", ["shared_login"])
        b["quality_flags"][0]["of"] = "pending"
        a["quality_flags"].append({"type": "shared_login", "of": "pending"})
        inactive = [h for h in hcps if h["status"] == "npi_deactivated" and h["deactivated_on"] < str(START)]
        for h in rng.sample(inactive, min(2, len(inactive))):
            session(h, when(), "direct", None, h["state"], "dosing", ["inactive_prescriber_login"])
        rec = session(None, when(), "search", None, rng.choice(states), "home", ["gated_page_unverified"])
        rec["page_views"].append({"page": "efficacy", "offset": rec["page_views"][-1]["offset"] + rec["page_views"][-1]["seconds"] + 3,
                                  "seconds": rng.randrange(20, 90)})

        out.sort(key=lambda r: (r["started_at"], r["hcp_id"] or ""))
        for i, r in enumerate(out):
            r["id"] = self.make_id(i)
        # The two halves of a shared login point at each other.
        pair = [r for r in out if any(f["type"] == "shared_login" for f in r["quality_flags"])]
        pair[0]["quality_flags"][-1]["of"], pair[1]["quality_flags"][-1]["of"] = pair[1]["id"], pair[0]["id"]
        return out
