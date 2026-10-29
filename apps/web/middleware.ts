import { NextResponse, type NextRequest } from "next/server";

const LANGS = ["nl", "en", "ru"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const first = pathname.split("/")[1];
  if (LANGS.includes(first)) {
    const res = NextResponse.next();
    res.cookies.set("lozhka_lang", first, { path: "/", maxAge: 31536000 });
    return res;
  }
  const saved = req.cookies.get("lozhka_lang")?.value;
  const accept = (req.headers.get("accept-language") ?? "").slice(0, 2);
  const lang = saved && LANGS.includes(saved) ? saved : LANGS.includes(accept) ? accept : "nl";
  const url = req.nextUrl.clone();
  url.pathname = `/${lang}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = { matcher: ["/((?!api|media|_next|pay|.*\\..*).*)"] };
