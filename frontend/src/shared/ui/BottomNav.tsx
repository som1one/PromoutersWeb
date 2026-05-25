import { NavLink } from 'react-router-dom';

type BottomNavItem = {
  to: string;
  label: string;
  icon: string;
};

type BottomNavProps = {
  items: readonly BottomNavItem[];
};

export function BottomNav({ items }: BottomNavProps) {
  return (
    <nav className="bottom-nav" aria-label="Мобильная навигация">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/app' || item.to === '/app/profile'}
          className={({ isActive }) =>
            `bottom-nav-link${isActive ? ' bottom-nav-link-active' : ''}`
          }
        >
          <span className={`nav-icon nav-icon-${item.icon}`} aria-hidden="true" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
