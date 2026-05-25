import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import {
  addMasterRequestComment,
  changeMasterRequestStatus,
  fetchMasterRequests,
  uploadMasterRequestAttachment,
  type MasterRequestRecord,
  type MasterRequestStatus,
} from '../../shared/api/master-requests';
import {
  formatDateTime,
  masterRequestStatusLabel,
  masterRequestStatusTone,
} from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import {
  Accordion,
  AppButton,
  EmptyState,
  MetricCard,
  PageIntro,
  SectionTitle,
  StatusPill,
  Surface,
  TextArea,
  TextInput,
} from '../../shared/ui/AppUI';

const NEXT_STATUS_BY_CURRENT: Record<MasterRequestStatus, MasterRequestStatus[]> = {
  new: ['accepted', 'cancelled'],
  accepted: ['on_the_way', 'cancelled'],
  on_the_way: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'cancelled'],
  completed: ['handed_over'],
  handed_over: [],
  cancelled: [],
};

function getCoords(): Promise<{ latitude: number; longitude: number } | null> {
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  });
}

export function MasterRequestsPage() {
  const { accessToken, user } = useAuth();
  const { showToast } = useToast();
  const [requests, setRequests] = useState<MasterRequestRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyRequestId, setBusyRequestId] = useState<string | null>(null);
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({});
  const [bsoComments, setBsoComments] = useState<Record<string, string>>({});

  const reload = async (token: string) => {
    setIsLoading(true);
    try {
      const records = await fetchMasterRequests(token);
      setRequests(records);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось загрузить заявки',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!accessToken) return;
    void reload(accessToken);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const counts = useMemo(() => {
    return requests.reduce(
      (acc, item) => {
        acc.total += 1;
        if (item.status === 'in_progress' || item.status === 'on_the_way') {
          acc.active += 1;
        }
        if (item.status === 'handed_over') {
          acc.handed += 1;
        }
        return acc;
      },
      { total: 0, active: 0, handed: 0 },
    );
  }, [requests]);

  const handleStatusChange = async (
    request: MasterRequestRecord,
    status: MasterRequestStatus,
  ) => {
    if (!accessToken) return;
    setBusyRequestId(request.id);
    try {
      const coords =
        status === 'on_the_way' || status === 'in_progress' ? await getCoords() : null;
      await changeMasterRequestStatus(accessToken, request.id, {
        status,
        latitude: coords?.latitude ?? null,
        longitude: coords?.longitude ?? null,
        captured_at: new Date().toISOString(),
      });
      showToast({ tone: 'info', title: `Статус: ${masterRequestStatusLabel(status)}` });
      await reload(accessToken);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось изменить статус',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusyRequestId(null);
    }
  };

  const handleCommentSubmit = async (
    requestId: string,
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    if (!accessToken) return;
    const body = (commentDrafts[requestId] ?? '').trim();
    if (!body) return;
    try {
      await addMasterRequestComment(accessToken, requestId, body);
      setCommentDrafts((prev) => ({ ...prev, [requestId]: '' }));
      await reload(accessToken);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось добавить комментарий',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  };

  const handleBsoUpload = async (requestId: string, file: File | null) => {
    if (!accessToken || !file) return;
    try {
      await uploadMasterRequestAttachment(
        accessToken,
        requestId,
        file,
        'bso',
        bsoComments[requestId],
      );
      setBsoComments((prev) => ({ ...prev, [requestId]: '' }));
      showToast({ tone: 'info', title: 'БСО прикреплён' });
      await reload(accessToken);
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось прикрепить БСО',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Кабинет мастера"
        title="Заявки на работы"
        description="Меняйте статус, прикрепляйте БСО и оставляйте комментарии. Геопозиция включается автоматически на «в пути» и «в работе»."
      />

      <div className="metric-strip">
        <MetricCard label="Всего" value={String(counts.total)} note="Видимые заявки" />
        <MetricCard label="В работе" value={String(counts.active)} note="С активным гео" />
        <MetricCard label="Закрыто" value={String(counts.handed)} note="Сдано на СД" />
      </div>

      <Surface>
        <SectionTitle
          title={isLoading ? 'Загрузка заявок...' : `${requests.length} заявок`}
          subtitle="Доступные в вашем филиале"
        />

        {isLoading ? (
          <EmptyState title="Собираем данные" />
        ) : requests.length === 0 ? (
          <EmptyState
            title="Заявок пока нет"
            description="Новые задания появятся здесь автоматически."
          />
        ) : (
          <div className="list-stack">
            {requests.map((request) => {
              const allowedStatuses = NEXT_STATUS_BY_CURRENT[request.status] ?? [];
              return (
                <article key={request.id} className="list-card">
                  <div className="list-card-top">
                    <strong>{request.title}</strong>
                    <StatusPill tone={masterRequestStatusTone(request.status)}>
                      {masterRequestStatusLabel(request.status)}
                    </StatusPill>
                  </div>

                  <div className="detail-list">
                    <div className="detail-row">
                      <span>Клиент</span>
                      <strong>{request.client_name ?? '—'}</strong>
                    </div>
                    {request.client_phone ? (
                      <div className="detail-row">
                        <span>Телефон</span>
                        <strong>{request.client_phone}</strong>
                      </div>
                    ) : null}
                    {request.address ? (
                      <div className="detail-row">
                        <span>Адрес</span>
                        <strong>{request.address}</strong>
                      </div>
                    ) : null}
                    <div className="detail-row">
                      <span>Мастер</span>
                      <strong>{request.assignee_name ?? 'Не назначен'}</strong>
                    </div>
                    {request.geo_tracking_enabled && request.last_known_at ? (
                      <div className="detail-row">
                        <span>GPS</span>
                        <strong>
                          {Number(request.last_known_latitude).toFixed(4)},{' '}
                          {Number(request.last_known_longitude).toFixed(4)}
                        </strong>
                      </div>
                    ) : null}
                  </div>

                  {allowedStatuses.length ? (
                    <div className="action-row">
                      {allowedStatuses.map((status) => (
                        <AppButton
                          key={status}
                          variant="ghost"
                          type="button"
                          disabled={busyRequestId === request.id}
                          onClick={() => handleStatusChange(request, status)}
                        >
                          {masterRequestStatusLabel(status)}
                        </AppButton>
                      ))}
                    </div>
                  ) : null}

                  <Accordion
                    title="Комментарии"
                    subtitle={`${request.comments.length} записей`}
                  >
                    {request.comments.length ? (
                      <div className="list-stack">
                        {request.comments.map((comment) => (
                          <div key={comment.id} className="list-card list-card-tight">
                            <strong>{comment.author_name}</strong>
                            <p>{comment.body}</p>
                            <span>{formatDateTime(comment.created_at)}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="Комментариев пока нет" />
                    )}
                    <form
                      onSubmit={(event) => handleCommentSubmit(request.id, event)}
                      className="auth-form"
                    >
                      <TextArea
                        label="Новый комментарий"
                        value={commentDrafts[request.id] ?? ''}
                        onChange={(event) =>
                          setCommentDrafts((prev) => ({
                            ...prev,
                            [request.id]: event.target.value,
                          }))
                        }
                        placeholder="Текст комментария"
                      />
                      <AppButton type="submit">Отправить</AppButton>
                    </form>
                  </Accordion>

                  <Accordion
                    title="История статусов"
                    subtitle={`${request.status_logs.length} переходов`}
                  >
                    {request.status_logs.length ? (
                      <div className="list-stack">
                        {request.status_logs.map((log) => (
                          <div key={log.id} className="list-card list-card-tight">
                            <strong>
                              {log.from_status
                                ? `${masterRequestStatusLabel(log.from_status)} → ${masterRequestStatusLabel(log.to_status)}`
                                : `Создание: ${masterRequestStatusLabel(log.to_status)}`}
                            </strong>
                            <p>{log.changed_by_name ?? 'system'}</p>
                            {log.note ? <p>{log.note}</p> : null}
                            <span>{formatDateTime(log.created_at)}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="История ещё пуста" />
                    )}
                  </Accordion>

                  {request.status === 'in_progress' ||
                  request.status === 'completed' ||
                  request.status === 'handed_over' ? (
                    <Accordion
                      title="БСО и документы"
                      subtitle={`${request.attachments.length} файлов`}
                    >
                      {request.attachments.length ? (
                        <div className="list-stack">
                          {request.attachments.map((attachment) => (
                            <div
                              key={attachment.id}
                              className="list-card list-card-tight"
                            >
                              <div className="list-card-top">
                                <strong>{attachment.filename}</strong>
                                <a
                                  className="chip-link"
                                  href={attachment.file_url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Открыть
                                </a>
                              </div>
                              {attachment.comment ? <p>{attachment.comment}</p> : null}
                              <span>{formatDateTime(attachment.created_at)}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyState title="Файлов пока нет" />
                      )}
                      <div className="auth-form">
                        <TextInput
                          label="Комментарий к файлу"
                          value={bsoComments[request.id] ?? ''}
                          onChange={(event) =>
                            setBsoComments((prev) => ({
                              ...prev,
                              [request.id]: event.target.value,
                            }))
                          }
                          placeholder="Например, оплата, акт, договор"
                        />
                        <label className="file-upload">
                          <span className="file-upload-label">Прикрепить файл</span>
                          <input
                            type="file"
                            onChange={(event) =>
                              handleBsoUpload(
                                request.id,
                                event.target.files?.[0] ?? null,
                              )
                            }
                          />
                        </label>
                      </div>
                    </Accordion>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </Surface>
    </div>
  );
}
