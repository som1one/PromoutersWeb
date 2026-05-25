import type { ChangeEvent } from 'react';

import type { RoutePointInput } from '../api/routes';
import { Button } from './Button';
import { Card } from './Card';

type RoutePointsEditorProps = {
  points: RoutePointInput[];
  onChange: (points: RoutePointInput[]) => void;
};

const pointTypes = [
  { value: 'start', label: 'Старт' },
  { value: 'checkpoint', label: 'Чекпоинт' },
  { value: 'stop', label: 'Остановка' },
  { value: 'finish', label: 'Финиш' },
] as const;

function nextPointType(points: RoutePointInput[]) {
  if (!points.length) {
    return 'start';
  }
  return points.length === 1 ? 'finish' : 'checkpoint';
}

export function RoutePointsEditor({ points, onChange }: RoutePointsEditorProps) {
  const updatePoint = <K extends keyof RoutePointInput>(
    pointIndex: number,
    key: K,
    value: RoutePointInput[K],
  ) => {
    const nextPoints = points.map((point, index) =>
      index === pointIndex ? { ...point, [key]: value } : point,
    );
    onChange(nextPoints);
  };

  const addPoint = () => {
    const nextSequence = points.length + 1;
    onChange([
      ...points,
      {
        sequence: nextSequence,
        name: '',
        address: '',
        latitude: null,
        longitude: null,
        point_type: nextPointType(points),
        planned_arrival_at: null,
        notes: '',
      },
    ]);
  };

  const removePoint = (pointIndex: number) => {
    const nextPoints = points
      .filter((_, index) => index !== pointIndex)
      .map((point, index) => ({
        ...point,
        sequence: index + 1,
      }));
    onChange(nextPoints);
  };

  const onNumberChange = (event: ChangeEvent<HTMLInputElement>, pointIndex: number, key: 'latitude' | 'longitude') => {
    const rawValue = event.target.value.trim();
    updatePoint(pointIndex, key, rawValue ? Number(rawValue) : null);
  };

  return (
    <div className="stack compact">
      {points.map((point, index) => (
        <Card key={`${point.sequence}-${index}`} className="route-editor-card">
          <div className="route-editor-head">
            <strong>Точка {index + 1}</strong>
            <Button
              variant="ghost"
              onClick={() => removePoint(index)}
              disabled={points.length <= 2}
            >
              Удалить
            </Button>
          </div>

          <div className="route-editor-grid">
            <label className="field">
              <span>Название</span>
              <input
                className="field-input"
                value={point.name}
                onChange={(event) => updatePoint(index, 'name', event.target.value)}
                placeholder="Например, ТЦ Dana Mall"
              />
            </label>

            <label className="field">
              <span>Тип точки</span>
              <select
                className="field-input field-select"
                value={point.point_type}
                onChange={(event) =>
                  updatePoint(index, 'point_type', event.target.value as RoutePointInput['point_type'])
                }
              >
                {pointTypes.map((pointType) => (
                  <option key={pointType.value} value={pointType.value}>
                    {pointType.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field route-editor-grid-full">
              <span>Адрес</span>
              <input
                className="field-input"
                value={point.address}
                onChange={(event) => updatePoint(index, 'address', event.target.value)}
                placeholder="Улица, дом, ориентир"
              />
            </label>

            <label className="field">
              <span>Широта</span>
              <input
                className="field-input"
                type="number"
                step="0.000001"
                value={point.latitude ?? ''}
                onChange={(event) => onNumberChange(event, index, 'latitude')}
                placeholder="53.900000"
              />
            </label>

            <label className="field">
              <span>Долгота</span>
              <input
                className="field-input"
                type="number"
                step="0.000001"
                value={point.longitude ?? ''}
                onChange={(event) => onNumberChange(event, index, 'longitude')}
                placeholder="27.566700"
              />
            </label>

            <label className="field">
              <span>Плановое время</span>
              <input
                className="field-input"
                type="datetime-local"
                value={point.planned_arrival_at ?? ''}
                onChange={(event) =>
                  updatePoint(index, 'planned_arrival_at', event.target.value || null)
                }
              />
            </label>

            <label className="field route-editor-grid-full">
              <span>Заметки</span>
              <textarea
                className="field-input field-textarea"
                value={point.notes}
                onChange={(event) => updatePoint(index, 'notes', event.target.value)}
                placeholder="Что важно проверить или снять на фото"
              />
            </label>
          </div>
        </Card>
      ))}

      <Button variant="secondary" onClick={addPoint}>
        Добавить точку
      </Button>
    </div>
  );
}
