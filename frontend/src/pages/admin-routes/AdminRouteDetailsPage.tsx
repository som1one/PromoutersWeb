import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { reviewPhoto } from '../../shared/api/photos';
import { fetchSessionGeoPings, type GeoPingRecord } from '../../shared/api/sessions';
import {
  assignRoute,
  cancelRoute,
  fetchAvailablePromoters,
  fetchRoute,
  fetchRoutePhotos,
  fetchRouteReport,
  updateRoute,
  type AvailablePromoter,
  type PhotoReport,
  type RouteRecord,
  type RouteReport,
} from '../../shared/api/routes';
import { useToast } from '../../shared/toast/useToast';
import {
  formatDate,
  formatDateTime,
  photoStatusLabel,
  photoStatusTone,
  pointTypeLabel,
  routeStatusLabel,
  routeStatusTone,
} from '../../shared/route-utils';
import {
  Accordion,
  AppButton,
  EmptyState,
  InfoGrid,
  PageIntro,
  SelectField,
  StatusPill,
  Surface,
  TextArea,
  TextInput,
} from '../../shared/ui/AppUI';
import { RouteMap } from '../../shared/ui/RouteMap';

export function AdminRouteDetailsPage() {
  const routeId = useParams().routeId ?? '';
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const [route, setRoute] = useState<RouteRecord | null>(null);
  const [photos, setPhotos] = useState<PhotoReport[]>([]);
  const [geoPings, setGeoPings] = useState<GeoPingRecord[]>([]);
  const [report, setReport] = useState<RouteReport | null>(null);
  const [promoters, setPromoters] = useState<AvailablePromoter[]>([]);
  const [assignPromoterId, setAssignPromoterId] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editWorkDate, setEditWorkDate] = useState('');
  const [editPlannedStart, setEditPlannedStart] = useState('');
  const [editPlannedEnd, setEditPlannedEnd] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function syncEditState(nextRoute: RouteRecord) {
    setEditTitle(nextRoute.title);
    setEditDescription(nextRoute.description ?? '');
    setEditWorkDate(nextRoute.work_date.slice(0, 10));
    setEditPlannedStart(
      nextRoute.planned_start_at ? nextRoute.planned_start_at.slice(0, 16) : '',
    );
    setEditPlannedEnd(
      nextRoute.planned_end_at ? nextRoute.planned_end_at.slice(0, 16) : '',
    );
  }

  async function loadRouteData() {
    if (!accessToken || !routeId) {
      return;
    }

    const [nextRoute, nextPromoters, nextPhotos] = await Promise.all([
      fetchRoute(accessToken, routeId),
      fetchAvailablePromoters(accessToken),
      fetchRoutePhotos(accessToken, routeId),
    ]);

    setRoute(nextRoute);
    setPromoters(nextPromoters);
    setPhotos(nextPhotos);
    setAssignPromoterId(nextRoute.promoter_id ?? '');
    syncEditState(nextRoute);

    if (nextRoute.current_session) {
      setGeoPings(await fetchSessionGeoPings(accessToken, nextRoute.current_session.id));
    } else {
      setGeoPings([]);
    }

    if (nextRoute.status === 'completed') {
      try {
        setReport(await fetchRouteReport(accessToken, routeId));
      } catch {
        setReport(null);
      }
    } else {
      setReport(null);
    }
  }

  useEffect(() => {
    if (!accessToken || !routeId) {
      return;
    }

    let cancelled = false;
    const token = accessToken;
    const currentRouteId = routeId;

    async function load() {
      try {
        const [nextRoute, nextPromoters, nextPhotos] = await Promise.all([
          fetchRoute(token, currentRouteId),
          fetchAvailablePromoters(token),
          fetchRoutePhotos(token, currentRouteId),
        ]);

        if (cancelled) {
          return;
        }

        setRoute(nextRoute);
        setPromoters(nextPromoters);
        setPhotos(nextPhotos);
        setAssignPromoterId(nextRoute.promoter_id ?? '');
        syncEditState(nextRoute);

        if (nextRoute.current_session) {
          const nextGeoPings = await fetchSessionGeoPings(token, nextRoute.current_session.id);
          if (!cancelled) {
            setGeoPings(nextGeoPings);
          }
        } else if (!cancelled) {
          setGeoPings([]);
        }

        if (nextRoute.status === 'completed') {
          try {
            const nextReport = await fetchRouteReport(token, currentRouteId);
            if (!cancelled) {
              setReport(nextReport);
            }
          } catch {
            if (!cancelled) {
              setReport(null);
            }
          }
        } else if (!cancelled) {
          setReport(null);
        }
      } catch (error) {
        if (!cancelled) {
          showToast({
            tone: 'error',
            title: 'Не удалось загрузить карточку маршрута',
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
  }, [accessToken, routeId, showToast]);

  async function handleAssignPromoter() {
    if (!accessToken || !assignPromoterId || !routeId) {
      return;
    }

    setIsSubmitting(true);
    try {
      await assignRoute(accessToken, routeId, { promoter_id: assignPromoterId });
      await loadRouteData();
      showToast({
        tone: 'success',
        title: 'Промоутер назначен',
      });
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось назначить промоутера',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCancelRoute() {
    if (!accessToken || !routeId) {
      return;
    }

    setIsSubmitting(true);
    try {
      await cancelRoute(accessToken, routeId);
      await loadRouteData();
      showToast({
        tone: 'success',
        title: 'Маршрут отменен',
      });
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось отменить маршрут',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePhotoReview(photoId: string, status: 'accepted' | 'rejected') {
    if (!accessToken) {
      return;
    }

    try {
      await reviewPhoto(accessToken, photoId, status);
      await loadRouteData();
      showToast({
        tone: 'success',
        title: status === 'accepted' ? 'Фото принято' : 'Фото отклонено',
      });
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось обновить фото',
        description: error instanceof Error ? error.message : undefined,
      });
    }
  }

  async function handleSaveRouteEdits() {
    if (!accessToken || !routeId || !route) return;
    setIsSubmitting(true);
    try {
      await updateRoute(accessToken, routeId, {
        title: editTitle.trim() || route.title,
        description: editDescription.trim(),
        work_date: editWorkDate || route.work_date,
        planned_start_at: editPlannedStart
          ? new Date(editPlannedStart).toISOString()
          : null,
        planned_end_at: editPlannedEnd
          ? new Date(editPlannedEnd).toISOString()
          : null,
      });
      await loadRouteData();
      showToast({ tone: 'success', title: 'Маршрут обновлён' });
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось сохранить изменения',
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <Surface>
        <EmptyState title="Открываем карточку маршрута" />
      </Surface>
    );
  }

  if (!route) {
    return (
      <Surface>
        <EmptyState title="Маршрут не найден" />
      </Surface>
    );
  }

  const branchPromoters = promoters.filter((promoter) => promoter.branch_id === route.branch_id);

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Управление маршрутом"
        title={route.title}
        description={`${formatDate(route.work_date)} · ${route.branch_name}`}
      />

      <Surface>
        <InfoGrid
          items={[
            {
              label: 'Статус',
              value: <StatusPill tone={routeStatusTone(route.status)}>{routeStatusLabel(route.status)}</StatusPill>,
            },
            { label: 'Промоутер', value: route.promoter_name || 'Не назначен' },
            { label: 'Фото', value: route.photo_count },
            { label: 'GPS', value: route.geo_ping_count },
          ]}
        />
      </Surface>

      <Surface>
        <RouteMap route={route} photos={photos} geoPings={geoPings} />
      </Surface>

      <Surface>
        <Accordion title="Редактирование" subtitle="Название, описание, даты">
          <div className="form-grid">
            <TextInput
              className="field-wide"
              label="Название"
              value={editTitle}
              onChange={(event) => setEditTitle(event.target.value)}
            />
            <TextArea
              className="field-wide"
              label="Описание"
              value={editDescription}
              onChange={(event) => setEditDescription(event.target.value)}
              placeholder="Краткое описание задачи или ориентиры маршрута"
            />
            <TextInput
              label="Дата работы"
              type="date"
              value={editWorkDate}
              onChange={(event) => setEditWorkDate(event.target.value)}
            />
            <TextInput
              label="Старт"
              type="datetime-local"
              value={editPlannedStart}
              onChange={(event) => setEditPlannedStart(event.target.value)}
            />
            <TextInput
              label="Окончание"
              type="datetime-local"
              value={editPlannedEnd}
              onChange={(event) => setEditPlannedEnd(event.target.value)}
            />
          </div>
          <div className="action-row">
            <AppButton
              type="button"
              onClick={() => void handleSaveRouteEdits()}
              disabled={isSubmitting}
            >
              Сохранить изменения
            </AppButton>
            <AppButton
              type="button"
              variant="ghost"
              onClick={() => syncEditState(route)}
              disabled={isSubmitting}
            >
              Сбросить
            </AppButton>
          </div>
        </Accordion>

        <Accordion title="Назначение" subtitle="Короткое действие" defaultOpen>
          <div className="form-grid">
            <SelectField
              className="field-wide"
              label="Промоутер"
              value={assignPromoterId}
              onChange={(event) => setAssignPromoterId(event.target.value)}
            >
              <option value="">Выберите промоутера</option>
              {branchPromoters.map((promoter) => (
                <option key={promoter.id} value={promoter.id}>
                  {promoter.full_name}
                </option>
              ))}
            </SelectField>
          </div>
          <div className="action-row">
            <AppButton type="button" onClick={() => void handleAssignPromoter()} disabled={isSubmitting || !assignPromoterId}>
              Сохранить назначение
            </AppButton>
            {(route.status === 'draft' || route.status === 'assigned') ? (
              <AppButton type="button" variant="ghost" onClick={() => void handleCancelRoute()} disabled={isSubmitting}>
                Отменить маршрут
              </AppButton>
            ) : null}
          </div>
        </Accordion>

        <Accordion title="Точки маршрута" subtitle={`${route.points.length} адресов`}>
          <div className="list-stack">
            {route.points.map((point) => (
              <article key={point.id} className="list-card list-card-tight">
                <div className="list-card-top">
                  <strong>{point.sequence}. {point.name}</strong>
                  <StatusPill tone="neutral">{pointTypeLabel(point.point_type)}</StatusPill>
                </div>
                <p>{point.address || 'Адрес не указан'}</p>
              </article>
            ))}
          </div>
        </Accordion>

        <Accordion title="GPS хронология" subtitle={`${geoPings.length} точек`}>
          {geoPings.length ? (
            <div className="list-stack">
              {geoPings.map((geoPing) => (
                <article key={geoPing.id} className="list-card list-card-tight">
                  <strong>{geoPing.point_name || 'GPS точка'}</strong>
                  <p>{geoPing.latitude}, {geoPing.longitude}</p>
                  <span>{formatDateTime(geoPing.captured_at)}</span>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="GPS история пока пуста" />
          )}
        </Accordion>

        <Accordion title="Фотоотчеты" subtitle={`${photos.length} файлов`}>
          {photos.length ? (
            <div className="gallery-grid">
              {photos.map((photo) => (
                <article key={photo.id} className="media-card">
                  <img src={photo.file_url} alt={photo.point_name || route.title} />
                  <div className="media-card-body">
                    <div className="list-card-top">
                      <strong>{photo.point_name || 'Фото по маршруту'}</strong>
                      <StatusPill tone={photoStatusTone(photo.status)}>
                        {photoStatusLabel(photo.status)}
                      </StatusPill>
                    </div>
                    <p>{photo.notes || 'Без комментария'}</p>
                    <span>{formatDateTime(photo.captured_at)}</span>
                    <div className="action-row">
                      <AppButton type="button" variant="secondary" onClick={() => void handlePhotoReview(photo.id, 'accepted')}>
                        Принять
                      </AppButton>
                      <AppButton type="button" variant="ghost" onClick={() => void handlePhotoReview(photo.id, 'rejected')}>
                        Отклонить
                      </AppButton>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="Фото пока нет" />
          )}
        </Accordion>

        {report ? (
          <Accordion title="Итоговый отчет" subtitle={`${report.total_minutes} минут`}>
            <div className="detail-list">
              <div className="detail-row">
                <span>Листовки</span>
                <strong>{report.leaflet_count}</strong>
              </div>
              <div className="detail-row">
                <span>Фото</span>
                <strong>{report.photo_count}</strong>
              </div>
              <div className="detail-row">
                <span>GPS</span>
                <strong>{report.geo_ping_count}</strong>
              </div>
            </div>
            <p className="support-copy">{report.summary}</p>
          </Accordion>
        ) : null}
      </Surface>
    </div>
  );
}
