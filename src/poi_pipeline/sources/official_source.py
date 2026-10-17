"""Small official directory crawl plus explicit authority pages, without an LLM.

Only short, literal excerpts become evidence. Names must occur on fetched pages;
link discovery never manufactures coordinates, opening times or cultural tags.
"""
import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit
from .base import Source, SourceError
from ..models import RawCandidate
from ..normalization import clean

DIRECTORY = "https://www.westbund.com/cn/index/KEY-PROJECTS/show_list.html"
SEEDS = [
    ("https://www.westbund.com/cn/index/KEY-PROJECTS/detail_aa8Ec.html", ["龙美术馆(西岸馆)", "龙美术馆"], "venue"),
    ("https://www.westbund.com/cn/index/KEY-PROJECTS/detail_695y4T.html", ["西岸美术馆"], "venue"),
    ("https://www.westbund.com/cn/index/POPULAR-VENUES/detail_e9dD9.html", ["上海油罐艺术中心", "油罐艺术中心"], "venue"),
    ("https://www.westbund.com/cn/index/NEWS-CENTER/2022-1230.html", ["星美术馆"], "venue"),
    ("https://whlyj.sh.gov.cn/gqfc/20260904/89b6a38c04274b0fbfe300752f21c3e6.html", ["谷地花溪", "滨江滑板公园", "塔吊广场"], "public_space"),
    ("https://www.shanghai.gov.cn/xuhui/index.html", ["西岸穹顶艺术中心", "西岸梦中心"], "venue"),
]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts, self.links = [], []
        self.href, self.label = None, []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if tag == "a":
            self.href, self.label = dict(attrs).get("href"), []
        if tag in ("p", "div", "br", "h1", "h2", "li") and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
        if tag == "a" and self.href:
            self.links.append((self.href, clean("".join(self.label))))
            self.href = None
        if tag in ("p", "div", "h1", "h2", "li") and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)
            if self.href:
                self.label.append(text)


def extract_page(html, terms=(), *, substantive=False):
    parser = PageParser()
    parser.feed(html)
    lines = [clean(x) for x in "".join(parser.parts).splitlines() if clean(x)]
    excerpts = {}
    for term in terms:
        matches = []
        term_lines=[line for line in lines if term in line]
        if substantive and any(len(line)>=80 for line in term_lines):
            term_lines=[line for line in term_lines if len(line)>=80]
        for line in term_lines:
            if term in line:
                start = max(0, line.index(term) - 35)
                snippet = line[start:start + (320 if substantive else 180)]
                if snippet not in matches:
                    matches.append(snippet)
        excerpts[term] = matches[:3]
    return dict(excerpts=excerpts, links=[dict(href=h, label=l[:120]) for h, l in parser.links if l][:150])


def support_for(text):
    # Evidence indexing only. These are not final semantic tags or verified claims.
    supports = ["identity"]
    for category, words in (("history", ("原址", "改造", "前身", "曾经", "旧", "机场", "码头")),
                            ("public_space", ("公共", "广场", "滨江", "步道", "公园")),
                            ("access", ("免费", "预约", "门票", "地址")),
                            ("opening", ("开放时间", "营业时间", "闭馆"))):
        if any(word in text for word in words):
            supports.append(category)
    return supports


class OfficialSource(Source):
    name = "official"

    def __init__(self, http, config=None):
        super().__init__(http)
        self.config=config

    def collect(self):
        pages = [(t['url'],t['names'],t['entity_kind']) for t in self.config.official_source_targets] if self.config else list(SEEDS)
        try:
            if self.config:
                yield from self.collect_pages(pages)
                return
            directory = self.http.get(self.name, DIRECTORY, {"progress": "1"},
                                      transform=extract_page, cache_variant="official-directory-v1")
            seen = {p[0] for p in pages}
            for link in directory["response"]["links"]:
                url = urljoin(DIRECTORY, link["href"])
                label = re.sub(r"^(文化设施|公共环境|商业办公|综合开发|开发项目)\s*", "", link["label"]).strip()
                parsed = urlsplit(url)
                if (parsed.netloc == "www.westbund.com" and "/detail_" in parsed.path and not parsed.query
                        and url not in seen and 2 <= len(label) <= 35
                        and any(word in label for word in ("美术馆", "艺术", "公园", "广场", "公共开放空间", "梦中心", "剧院"))):
                    seen.add(url)
                    if label in ("公共开放空间", "西岸美术馆大道") or "保税仓库" in label:
                        continue  # directory overview/logistics, not a discrete visitor node
                    kind = "public_space" if any(w in label for w in ("公园", "广场", "公共")) else "venue"
                    pages.append((url, [label], kind))
                if len(pages) >= 20:
                    break
        except (SourceError, ValueError, TypeError, KeyError) as exc:
            self.error("official_directory", exc)
        yield from self.collect_pages(pages)

    def collect_pages(self, pages):
        for url, terms, kind in pages:
            try:
                result = self.http.get(self.name, url, transform=lambda html: extract_page(html, terms, substantive=bool(self.config)),
                                       cache_variant=("official-substantive-v2:" if self.config else "official-excerpts-v1:") + "|".join(terms))
                mentions = result["response"]["excerpts"]
                government = urlsplit(url).netloc.endswith(".gov.cn")
                matched = [t for t, excerpts in mentions.items() if excerpts]
                for term, snippets in mentions.items():
                    if not snippets:
                        self.errors.append(dict(source=self.name, request=url, status="name_not_found", name=term))
                        continue
                    if not government and term != matched[0]:
                        continue  # seed terms on a venue page are alternate names
                    evidence = [dict(text=s, supports=support_for(s), extraction="literal_excerpt; unverified temporal context") for s in snippets]
                    pid = hashlib.sha256((url + "#" + term).encode()).hexdigest()[:20]
                    yield RawCandidate(pid, "government" if government else "official",
                        urlsplit(url).netloc, url, result["retrieved_at"], name_zh=term,
                        aliases=[t for t in matched if t != term] if not government else [],
                        source_category="official_place_mention", snippets=evidence,
                        supports=sorted({s for item in evidence for s in item["supports"]}), entity_kind=kind)
            except (SourceError, ValueError, TypeError, KeyError) as exc:
                self.error(url, exc)
