import { useLocation } from "react-router-dom";

export default function Dashboard() {
  const { state } = useLocation();

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center px-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-8 text-center">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          Dashboard coming soon
        </h1>
        {state && (
          <div className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
            <p>
              <span className="font-medium text-gray-700 dark:text-gray-300">gameName:</span>{" "}
              {state.gameName}
            </p>
            <p>
              <span className="font-medium text-gray-700 dark:text-gray-300">puuid:</span>{" "}
              {state.puuid}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
