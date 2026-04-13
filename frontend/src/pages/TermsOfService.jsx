import { Link } from "react-router-dom";

export default function TermsOfService() {
  return (
    <div className="min-h-screen bg-[#05080f] pt-20 pb-16 px-6">
      <div className="max-w-2xl mx-auto">

        <div className="mb-10">
          <Link to="/" className="text-[#c89b3c] text-sm hover:underline">← Back to Rift IQ</Link>
          <h1 className="text-3xl font-extrabold text-white mt-4 mb-2">Terms of Service</h1>
          <p className="text-white/30 text-sm">Last updated: April 2026</p>
        </div>

        <div className="space-y-8 text-white/60 text-sm leading-relaxed">

          <section>
            <h2 className="text-white font-bold text-base mb-2">1. Acceptance of Terms</h2>
            <p>By using Rift IQ ("the Service"), you agree to these Terms of Service. If you do not agree, do not use the Service.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">2. Description of Service</h2>
            <p>Rift IQ is a League of Legends performance analytics and coaching tool. It uses the Riot Games API to retrieve publicly available match data, ranked statistics, and live game information associated with a player's Riot ID.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">3. Riot Games Affiliation</h2>
            <p>Rift IQ is not endorsed by, affiliated with, or officially connected to Riot Games, Inc. League of Legends and all related names, marks, and logos are trademarks of Riot Games, Inc. Use of the Riot Games API is subject to Riot's <a href="https://developer.riotgames.com/docs/portal" target="_blank" rel="noreferrer" className="text-[#c89b3c] hover:underline">developer policies</a>.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">4. Acceptable Use</h2>
            <p>You agree not to:</p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>Use the Service for any unlawful purpose</li>
              <li>Attempt to scrape, reverse-engineer, or abuse the Service</li>
              <li>Use the Service to harass or harm other players</li>
            </ul>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">5. Disclaimer of Warranties</h2>
            <p>The Service is provided "as is" without warranties of any kind. We do not guarantee accuracy, uptime, or availability. All data is sourced from the Riot Games API and may be delayed or incomplete.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">6. Limitation of Liability</h2>
            <p>To the maximum extent permitted by law, Rift IQ shall not be liable for any indirect, incidental, or consequential damages arising from your use of the Service.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">7. Changes to Terms</h2>
            <p>We may update these Terms at any time. Continued use of the Service after changes constitutes acceptance of the updated Terms.</p>
          </section>

          <section>
            <h2 className="text-white font-bold text-base mb-2">8. Contact</h2>
            <p>For questions about these Terms, please open an issue on our GitHub repository.</p>
          </section>

        </div>

        <div className="mt-12 pt-6 border-t border-white/[0.06] flex gap-6 text-xs text-white/25">
          <Link to="/privacy" className="hover:text-[#c89b3c] transition-colors">Privacy Policy</Link>
          <Link to="/" className="hover:text-[#c89b3c] transition-colors">Home</Link>
        </div>

      </div>
    </div>
  );
}
