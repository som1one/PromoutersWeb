import { useAuth } from '../../app/auth/useAuth';
import { IncomeExpensePage } from '../income-expense/IncomeExpensePage';
import { OwnerFinancePage } from './OwnerFinancePage';

export function FinanceRoutePage() {
  const { user } = useAuth();
  if (user?.roleCode === 'owner') {
    return <OwnerFinancePage />;
  }
  return <IncomeExpensePage />;
}
