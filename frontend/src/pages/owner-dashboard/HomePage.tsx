import { useAuth } from '../../app/auth/useAuth';
import { OverviewPage } from '../overview/OverviewPage';
import { OwnerDashboardPage } from './OwnerDashboardPage';

export function HomePage() {
  const { user } = useAuth();

  if (user?.roleCode === 'owner') {
    return <OwnerDashboardPage />;
  }

  return <OverviewPage />;
}
