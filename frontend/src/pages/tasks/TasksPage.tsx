import { tasks } from '../../shared/mocks/promoter-data';
import { Badge } from '../../shared/ui/Badge';
import { Button } from '../../shared/ui/Button';
import { Card } from '../../shared/ui/Card';
import { SectionHeading } from '../../shared/ui/SectionHeading';

export function TasksPage() {
  return (
    <div className="stack">
      <SectionHeading
        eyebrow="Задачи"
        title="Очередь действий по смене"
        description="Здесь уже есть основа под фотоотчёты, BSO, заявки мастеру и follow-up задачи."
      />

      <div className="tasks-grid">
        {tasks.map((task) => (
          <Card key={task.id} className="task-card">
            <div className="task-card-head">
              <Badge
                tone={
                  task.status === 'urgent'
                    ? 'warning'
                    : task.status === 'scheduled'
                      ? 'accent'
                      : 'neutral'
                }
              >
                {task.status === 'urgent'
                  ? 'срочно'
                  : task.status === 'scheduled'
                    ? 'по графику'
                    : 'в плане'}
              </Badge>
              <span>{task.meta}</span>
            </div>

            <h3>{task.title}</h3>

            <div className="task-card-actions">
              <Button variant="secondary">Открыть</Button>
              <Button variant="ghost">Отложить</Button>
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <SectionHeading
          eyebrow="Поток"
          title="Что можно подключить следующим шагом"
          description="На этом экране удобно развивать сценарии промоутера без ломки маршрутизации."
        />

        <div className="feature-list">
          <div>
            <strong>Фотоотчёты</strong>
            <p>Галерея, очередь на отправку, повторная модерация и ошибки загрузки.</p>
          </div>
          <div>
            <strong>Заявки мастеру</strong>
            <p>Создание запроса, статус выполнения, вложения и комментарии.</p>
          </div>
          <div>
            <strong>Подтверждение смены</strong>
            <p>Старт, завершение, геометки, таймер и сводка по листовкам.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
