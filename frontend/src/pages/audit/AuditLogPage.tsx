import { useEffect, useState } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import { fetchAuditLogs, type AuditLogRecord } from '../../shared/api/audit';
import { formatDateTime } from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import { EmptyState, PageIntro, SectionTitle, Surface } from '../../shared/ui/AppUI';

export function AuditLogPage() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [logs, setLogs] = useState<AuditLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    const token = accessToken;

    async function loadLogs() {
      try {
        const nextLogs = await fetchAuditLogs(token, { limit: 30 });
        if (!cancelled) {
          setLogs(nextLogs);
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось загрузить аудит',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadLogs();

    return () => {
      cancelled = true;
    };
  }, [accessToken, showToast]);

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Аудит"
        title="Последние действия"
        description="Компактная лента для контроля критичных событий."
      />

      <Surface>
        <SectionTitle title="Журнал" subtitle={isLoading ? 'Загрузка...' : `${logs.length} записей`} />

        {isLoading ? (
          <EmptyState title="Готовим журнал" />
        ) : logs.length ? (
          <div className="list-stack">
            {logs.map((log) => (
              <article key={log.id} className="list-card">
                <strong>{log.action}</strong>
                <p>{log.actor_username || 'system'} · {log.entity_type}</p>
                <p>{log.branch_name || 'Без филиала'}</p>
                <span>{formatDateTime(log.created_at)}</span>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Журнал пока пуст" />
        )}
      </Surface>
    </div>
  );
}
