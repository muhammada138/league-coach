import { Link } from "react-router-dom";

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-[#05080f] pt-20 pb-16 px-6">
      <div className="max-w-2xl mx-auto">

        <div className="mb-10">
          <Link to="/" className="text-[#c89b3c] text-sm hover:underline">← Back to Rift IQ</Link>
          <h1 className="text-3xl font-extrabold text-white mt-4 mb-2">Privacy Policy</h1>
          <p className="text-white/30 text-sm">Last updated: April 2026</p>
        </div>

        <div className="space-y-8 text-white/60 text-sm leading-relaxed">

          <section>
            <h2 className="text-white font-bold text-base mb-2">1. Overview</h2>
            <p>Rift IQ does not collect, store, or sell personal information. This policy explains what data is used and how.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">2. Data We Access</h2>
            <p>When you enter a Riot ID, we query the Riot Games API to retrieve:</p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>Summoner profile and rank information</li>
              <li>Match history and performance statistics</li>
              <li>Live game data (if applicable)</li>
            </ul>
            <p className="mt-2">This data is publicly accessible through the Riot Games API and is not private information.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">3. Data We Store</h2>
            <p><span className="text-white/80 font-semibold">On your device (localStorage):</span> Your recent search history and any profiles you choose to save are stored locally in your browser. This data never leaves your device and can be cleared at any time through your browser settings.</p>
            <p className="mt-2"><span className="text-white/80 font-semibold">On our servers:</span> We cache match and rank data from the Riot API to reduce load times. This data is tied to public Riot account identifiers (PUUIDs) and contains no personally identifiable information.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">4. Data We Do Not Collect</h2>
            <ul className="list-disc list-inside space-y-1">
              <li>Names, email addresses, or contact information</li>
              <li>Passwords or authentication credentials</li>
              <li>Payment information</li>
              <li>IP addresses or device fingerprints</li>
              <li>Tracking cookies or advertising identifiers</li>
            </ul>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">5. Third-Party Services</h2>
            <p>Rift IQ uses the following third-party services:</p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li><span className="text-white/80">Riot Games API</span> — source of all League of Legends data</li>
              <li><span className="text-white/80">Vercel</span> — frontend hosting and analytics (aggregate, anonymised)</li>
              <li><span className="text-white/80">Groq</span> — AI inference for coaching tips (match context only, no personal data)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">6. Cookies</h2>
            <p>Rift IQ does not use tracking cookies. Browser localStorage is used solely to persist your saved profiles and search history on your own device.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">7. Children's Privacy</h2>
            <p>Rift IQ is not directed at children under 13. We do not knowingly collect any information from children.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">8. Changes to This Policy</h2>
            <p>We may update this Privacy Policy from time to time. The date at the top of this page reflects the most recent revision.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">9. Contact</h2>
            <p>For privacy-related questions, please open an issue on our GitHub repository.</p>
          </section>

        </div>

        <div className="mt-12 pt-6 border-t border-white/[0.06] flex gap-6 text-xs text-white/25">
          <Link to="/terms" className="hover:text-[#c89b3c] transition-colors">Terms of Service</Link>
          <Link to="/" className="hover:text-[#c89b3c] transition-colors">Home</Link>
        </div>

      </div>
    </div>
  );
}
