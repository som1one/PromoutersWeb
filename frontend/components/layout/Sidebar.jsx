"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList, MapPin, Calculator } from "lucide-react";
import { getUser } from "@/lib/auth";

const MANAGER_ROLES = ["branch_manager", "ad_director", "owner"];

const NAV_ITEMS = [
  {
    href: "/admin/deals",
    label: "Заявки",
    icon: ClipboardList,
  },
  // {
  //   href: "/admin/routes",
  //   label: "Маршруты",
  //   icon: MapPin,
  //   roles: MANAGER_ROLES,
  // },
  {
    href: "/admin/settlements",
    label: "Расчёты",
    icon: Calculator,
    roles: MANAGER_ROLES,
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [userRole, setUserRole] = useState(null);

  useEffect(() => {
    const user = getUser();
    if (user?.role) {
      setUserRole(user.role);
    }
  }, []);

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || userRole && item.roles.includes(userRole)
  );

  return (
    <nav className="flex items-center gap-1 px-4 py-2 bg-slate-800/50 border-b border-slate-700/50">
      {visibleItems.map((item) => {
        const Icon = item.icon;
        const isActive = pathname?.startsWith(item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive
                ? "bg-purple-600 text-white"
                : "text-slate-300 hover:bg-slate-700 hover:text-white"
            }`}
          >
            <Icon className="w-4 h-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
