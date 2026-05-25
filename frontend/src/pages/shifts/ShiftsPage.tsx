import { timeline } from '../../shared/mocks/promoter-data';
import { Badge } from '../../shared/ui/Badge';
import { Button } from '../../shared/ui/Button';
import { Card } from '../../shared/ui/Card';
import { SectionHeading } from '../../shared/ui/SectionHeading';

export function ShiftsPage() {
  return (
    <div className="stack">
      <SectionHeading
        eyebrow="Смены"
        title="Маршрут на сегодня"
        description="Страница рассчитана на работу с одной руки: ключевые действия и статус смены всегда рядом."
        action={<Button variant="secondary">Отметить геопинг</Button>}
      />

      <Card className="highlight-card">
        <div className="highlight-row">
          <div>
            <p className="eyebrow">Активная смена</p>
            <h3>10:00 - 16:00</h3>
            <p className="section-description">
              Маршрут №24 по точкам в центре Минска. Запланировано 7 чекпоинтов и 18 фото.
            </p>
          </div>

          <Badge tone="positive">60% выполнено</Badge>
        </div>
      </Card>

      <div className="route-grid">
        {timeline.map((point, index) => (
          <Card key={point.id} className="route-card">
            <div className="route-card-head">
              <Badge tone={point.status === 'done' ? 'positive' : 'accent'}>
                {`Точка ${index + 1}`}
              </Badge>
              <strong>{point.time}</strong>
            </div>

            <h3>{point.title}</h3>
            <p>{point.address}</p>
            <div className="route-card-actions">
              <Button variant="ghost">Открыть карту</Button>
              <Button variant="secondary">Фотоотчёт</Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
