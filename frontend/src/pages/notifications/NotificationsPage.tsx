import { useEffect, useState } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import {
  fetchNotifications,
  markNotificationRead,
  type NotificationRecord,
} from '../../shared/api/notifications';
import { formatDateTime } from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import {
  AppButton,
  EmptyState,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
} from '../../shared/ui/AppUI';

export function NotificationsPage() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  async function loadNotifications() {
    if (!accessToken) {
      return;
    }

    const token = accessToken;
    const nextNotifications = await fetchNotifications(token);
    setNotifications(nextNotifications);
  }

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let cancelled = false;
    const token = accessToken;

    async function load() {
      try {
        const nextNotifications = await fetchNotifications(token);
        if (!cancelled) {
          setNotifications(nextNotifications);
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось загрузить уведомления',
            description: error instanceof Error ? error.message : undefined,
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [accessToken, showToast]);

  async function handleMarkRead(notificationId: string) {
    if (!accessToken) {
      return;
    }

    const token = accessToken;
    try {
      await markNotificationRead(token, notificationId);
      await loadNotifications();
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось обновить уведомление',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  }

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Сигналы"
        title="Лента уведомлений"
        description="Только текст и статус, чтобы быстро разобрать важное с телефона."
      />

      <Surface>
        <SectionTitle
          title="Все уведомления"
          subtitle={isLoading ? 'Загрузка...' : `${notifications.length} записей`}
        />

        {isLoading ? (
          <EmptyState title="Получаем сигналы" />
        ) : notifications.length ? (
          <div className="list-stack">
            {notifications.map((notification) => (
              <article key={notification.id} className="list-card">
                <div className="list-card-top">
                  <strong>{notification.title}</strong>
                  <StatusPill tone={notification.status === 'read' ? 'neutral' : 'accent'}>
                    {notification.status === 'read' ? 'Прочитано' : 'Новое'}
                  </StatusPill>
                </div>
                <p>{notification.body}</p>
                <span>{formatDateTime(notification.created_at)}</span>
                {notification.status !== 'read' ? (
                  <div className="action-row">
                    <AppButton type="button" variant="ghost" onClick={() => void handleMarkRead(notification.id)}>
                      Отметить прочитанным
                    </AppButton>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Уведомлений пока нет" />
        )}
      </Surface>
    </div>
  );
}
