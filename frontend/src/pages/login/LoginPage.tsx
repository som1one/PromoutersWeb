import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../app/auth/useAuth';
import { formatTime } from '../../shared/route-utils';
import { useToast } from '../../shared/toast/useToast';
import { AppButton, Surface, TextInput } from '../../shared/ui/AppUI';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, verifyCode, pendingChallenge, clearPendingChallenge } = useAuth();
  const { showToast } = useToast();
  const [phone, setPhone] = useState('+7');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isSmsStep = Boolean(pendingChallenge);

  const handleLoginSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      const result = await login({ phone, password });
      if (result.requiresSmsVerification) {
        showToast({
          tone: 'info',
          title: 'Код отправлен',
          description: 'Подтвердите вход кодом из SMS.',
        });
        return;
      }
      navigate('/app');
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Не удалось войти',
        description: error instanceof Error ? error.message : 'Проверьте телефон и пароль.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      await verifyCode({ code });
      navigate('/app');
    } catch (error) {
      showToast({
        tone: 'error',
        title: 'Код не подошёл',
        description: error instanceof Error ? error.message : 'Попробуйте ещё раз.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-scene">
      <Surface className="auth-card">
        <header className="auth-header">
          <div className="brand-mark brand-mark-large">СУ</div>
          <div>
            <span className="eyebrow">СУУПР</span>
            <h1 className="auth-title">Вход в систему</h1>
          </div>
        </header>

        {isSmsStep ? (
          <form className="auth-form" onSubmit={handleVerifySubmit}>
            <p className="auth-hint">
              Код отправлен в SMS. Активен до {formatTime(pendingChallenge?.expiresAt ?? null)}.
            </p>

            <TextInput
              label="Код из SMS"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="6-значный код"
              inputMode="numeric"
              autoComplete="one-time-code"
            />

            <AppButton type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Проверяем...' : 'Подтвердить'}
            </AppButton>

            <AppButton
              type="button"
              variant="ghost"
              onClick={() => {
                clearPendingChallenge();
                setCode('');
              }}
            >
              Изменить номер
            </AppButton>
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleLoginSubmit}>
            <TextInput
              label="Телефон"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="+7 999 000-00-00"
              autoComplete="tel"
              inputMode="tel"
            />

            <TextInput
              label="Пароль"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Введите пароль"
              type="password"
              autoComplete="current-password"
            />

            <AppButton type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Входим...' : 'Войти'}
            </AppButton>
          </form>
        )}
      </Surface>
    </div>
  );
}
