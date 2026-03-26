import Link from "next/link"
import { MessageCircle, ArrowRight, CheckCircle } from "lucide-react"

const FEATURES = [
  "Track contributions and pool balance in real time",
  "AI-powered member risk scoring and insights",
  "Automated payment reminders via WhatsApp",
  "Exco dashboard with full withdrawal and broadcast controls",
]

export default function LandingPage() {
  const waNumber = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER ?? ""
  const waLink = `https://wa.me/${waNumber}`

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Nav */}
      <nav className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-white font-bold text-xs">A</span>
          </div>
          <span className="font-semibold text-foreground">AkoweAI</span>
        </div>
        <Link
          href="/login"
          className="text-sm font-medium text-primary hover:underline"
        >
          Exco Login
        </Link>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-20 text-center">
        <div className="max-w-lg space-y-6">
          <div className="inline-flex items-center gap-2 bg-primary/10 text-primary text-xs font-medium px-3 py-1.5 rounded-full">
            <MessageCircle className="w-3.5 h-3.5" />
            WhatsApp-first cooperative management
          </div>

          <h1 className="text-4xl font-bold text-foreground leading-tight tracking-tight">
            Manage your ajo &amp; esusu on WhatsApp
          </h1>

          <p className="text-muted-foreground text-lg leading-relaxed">
            AkoweAI brings your cooperative savings group into the digital age —
            contributions, reminders, and financial insights, all without leaving
            WhatsApp.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a
              href={waLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 bg-[#25D366] text-white
                         font-medium px-6 py-3 rounded-lg hover:bg-[#1ebe5d] transition-colors text-sm"
            >
              <MessageCircle className="w-4 h-4" />
              Open in WhatsApp
            </a>
            <Link
              href="/login"
              className="inline-flex items-center justify-center gap-2 border border-border
                         text-foreground font-medium px-6 py-3 rounded-lg hover:bg-muted
                         transition-colors text-sm"
            >
              Exco Dashboard
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Features */}
        <div className="mt-20 max-w-md w-full">
          <ul className="space-y-3 text-left">
            {FEATURES.map((f) => (
              <li key={f} className="flex items-start gap-3">
                <CheckCircle className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <span className="text-sm text-muted-foreground">{f}</span>
              </li>
            ))}
          </ul>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border px-6 py-4 text-center">
        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} AkoweAI. Built for Nigeria&apos;s cooperative culture.
        </p>
      </footer>
    </div>
  )
}