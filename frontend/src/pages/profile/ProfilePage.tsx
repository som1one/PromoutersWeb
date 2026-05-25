import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/auth/useAuth';
import { ApiError } from '../../shared/api/http';
import { roleCodeLabel } from '../../shared/route-utils';
import {
  AppButton,
  InlineNotice,
  PageIntro,
  SectionTitle,
  Surface,
  TextInput,
} from '../../shared/ui/AppUI';

type FormState = {
  firstName: string;
  lastName: string;
  middleName: string;
  email: string;
  phone: string;
  password: string;
  passwordConfirm: string;
};

function buildInitialState(
  source: {
    firstName: string;
    lastName: string;
    middleName: string | null;
    email: string;
    phone: string;
  },
): FormState {
  return {
    firstName: source.firstName,
    lastName: source.lastName,
    middleName: source.middleName ?? '',
    email: source.email,
    phone: source.phone,
    password: '',
    passwordConfirm: '',
  };
}

export function ProfilePage() {
  const { user, logout, updateProfile } = useAuth();

  const initial = useMemo(() => {
    if (!user) return null;
    return buildInitialState(user);
  }, [user]);

  const [form, setForm] = useState<FormState | null>(initial);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    setForm(initial);
  }, [initial]);

  if (!user || !form) {
    return null;
  }

  const fullName = [user.lastName, user.firstName].filter(Boolean).join(' ') || user.username;
  const initials =
    `${(user.firstName?.[0] ?? '').toUpperCase()}${(user.lastName?.[0] ?? '').toUpperCase()}` ||
    (user.username || '?').slice(0, 2).toUpperCase();

  const isDirty =
    initial !== null &&
    (form.firstName !== initial.firstName ||
      form.lastName !== initial.lastName ||
      form.middleName !== initial.middleName ||
      form.email !== initial.email ||
      form.phone !== initial.phone ||
      form.password.length > 0 ||
      form.passwordConfirm.length > 0);

  const updateField = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setForm((prev) => (prev ? { ...prev, [field]: value } : prev));
    setSuccess(null);
    setError(null);
  };

  const handleReset = () => {
    if (initial) {
      setForm(initial);
      setError(null);
      setSuccess(null);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!initial) return;

    if (!form.firstName.trim() || !form.lastName.trim()) {
      setError('Имя и фамилия обязательны.');
      return;
    }
    if (!form.email.trim()) {
      setError('Email обязателен.');
      return;
    }
    if (form.password || form.passwordConfirm) {
      if (form.password.length < 8) {
        setError('Пароль должен быть не короче 8 символов.');
        return;
      }
      if (form.password !== form.passwordConfirm) {
        setError('Пароли не совпадают.');
        return;
      }
    }

    const payload: Parameters<typeof updateProfile>[0] = {};
    if (form.firstName !== initial.firstName) payload.firstName = form.firstName.trim();
    if (form.lastName !== initial.lastName) payload.lastName = form.lastName.trim();
    if (form.middleName !== initial.middleName) {
      const trimmed = form.middleName.trim();
      payload.middleName = trimmed === '' ? null : trimmed;
    }
    if (form.email !== initial.email) payload.email = form.email.trim();
    if (form.phone !== initial.phone) {
      const trimmed = form.phone.trim();
      payload.phone = trimmed === '' ? null : trimmed;
    }
    if (form.password) payload.password = form.password;

    if (Object.keys(payload).length === 0) {
      setSuccess('Изменений нет.');
      return;
    }

    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await updateProfile(payload);
      setForm((prev) => (prev ? { ...prev, password: '', passwordConfirm: '' } : prev));
      setSuccess('Профиль обновлён.');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Не удалось сохранить изменения.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="page-stack">
      <PageIntro
        eyebrow="Профиль"
        title="Личные данные и доступ"
        description="Управляйте контактами и паролем входа."
      />

      <Surface className="profile-hero">
        <div className="profile-hero-row">
          <div className="profile-avatar" aria-hidden="true">
            {initials}
          </div>
          <div className="profile-hero-meta">
            <strong>{fullName}</strong>
            <span>{user.email}</span>
            <div className="profile-hero-tags">
              <span className="pill pill-accent">{roleCodeLabel(user.roleCode)}</span>
              <span className="pill pill-neutral">{user.branch}</span>
              {user.city ? <span className="pill pill-neutral">{user.city}</span> : null}
            </div>
          </div>
        </div>
      </Surface>

      <Surface>
        <SectionTitle title="Личные данные" subtitle="ФИО и контакты для связи." />
        <form className="profile-form" onSubmit={handleSubmit} noValidate>
          <div className="form-grid">
            <TextInput
              label="Фамилия"
              value={form.lastName}
              onChange={(event) => updateField('lastName', event.target.value)}
              autoComplete="family-name"
              required
            />
            <TextInput
              label="Имя"
              value={form.firstName}
              onChange={(event) => updateField('firstName', event.target.value)}
              autoComplete="given-name"
              required
            />
            <TextInput
              label="Отчество"
              value={form.middleName}
              onChange={(event) => updateField('middleName', event.target.value)}
              autoComplete="additional-name"
            />
            <TextInput
              label="Email"
              type="email"
              value={form.email}
              onChange={(event) => updateField('email', event.target.value)}
              autoComplete="email"
              required
            />
            <TextInput
              label="Телефон"
              type="tel"
              value={form.phone}
              onChange={(event) => updateField('phone', event.target.value)}
              autoComplete="tel"
              placeholder="+7XXXXXXXXXX"
            />
          </div>

          <SectionTitle
            title="Смена пароля"
            subtitle="Заполните, только если хотите обновить пароль."
          />
          <div className="form-grid">
            <TextInput
              label="Новый пароль"
              type="password"
              value={form.password}
              onChange={(event) => updateField('password', event.target.value)}
              autoComplete="new-password"
              minLength={8}
            />
            <TextInput
              label="Повторите пароль"
              type="password"
              value={form.passwordConfirm}
              onChange={(event) => updateField('passwordConfirm', event.target.value)}
              autoComplete="new-password"
              minLength={8}
            />
          </div>

          {error ? <InlineNotice tone="warning">{error}</InlineNotice> : null}
          {success ? <InlineNotice tone="positive">{success}</InlineNotice> : null}

          <div className="action-row">
            <AppButton type="submit" variant="primary" disabled={!isDirty || isSaving}>
              {isSaving ? 'Сохраняем…' : 'Сохранить изменения'}
            </AppButton>
            <AppButton
              type="button"
              variant="ghost"
              onClick={handleReset}
              disabled={!isDirty || isSaving}
            >
              Сбросить
            </AppButton>
          </div>
        </form>
      </Surface>

      <Surface>
        <SectionTitle title="Сессия" subtitle="Завершить текущую сессию на этом устройстве." />
        <div className="action-row">
          <AppButton type="button" variant="ghost" onClick={logout}>
            Выйти из кабинета
          </AppButton>
        </div>
      </Surface>
    </div>
  );
}
