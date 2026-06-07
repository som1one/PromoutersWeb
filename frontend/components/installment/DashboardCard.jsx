"use client";

export default function DashboardCard({ title, value, subtitle, icon, color = "purple", trend }) {
  const colorClasses = {
    purple: "bg-gradient-to-br from-purple-500/20 to-purple-600/20 border-purple-500/30",
    blue: "bg-gradient-to-br from-blue-500/20 to-blue-600/20 border-blue-500/30",
    green: "bg-gradient-to-br from-green-500/20 to-green-600/20 border-green-500/30",
    orange: "bg-gradient-to-br from-orange-500/20 to-orange-600/20 border-orange-500/30",
  };

  const iconColors = {
    purple: "text-purple-400",
    blue: "text-blue-400",
    green: "text-green-400",
    orange: "text-orange-400",
  };

  return (
    <div className={`rounded-xl border p-4 sm:p-6 ${colorClasses[color]} backdrop-blur-sm transition-all hover:scale-105 hover:shadow-lg`}>
      <div className="flex items-start justify-between mb-3 sm:mb-4">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
          {icon && (
            <div className={`p-2 sm:p-3 rounded-lg bg-white/5 ${iconColors[color]} flex-shrink-0`}>
              {icon}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-xs sm:text-sm text-dashboard-text-muted font-medium truncate">{title}</p>
            {subtitle && (
              <p className="text-[10px] sm:text-xs text-dashboard-text-muted/70 mt-0.5 sm:mt-1 truncate">{subtitle}</p>
            )}
          </div>
        </div>
        {trend && (
          <div className={`text-[10px] sm:text-xs font-semibold px-1.5 sm:px-2 py-0.5 sm:py-1 rounded flex-shrink-0 ${
            trend > 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
          }`}>
            {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div className="mt-3 sm:mt-4">
        <p className="text-2xl sm:text-3xl font-bold text-white break-words">{value}</p>
      </div>
    </div>
  );
}

