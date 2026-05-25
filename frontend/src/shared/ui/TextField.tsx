import type { InputHTMLAttributes } from 'react';

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
};

export function TextField({ label, hint, id, ...props }: TextFieldProps) {
  const fieldId = id ?? label.toLowerCase().replaceAll(' ', '-');

  return (
    <label className="field" htmlFor={fieldId}>
      <span>{label}</span>
      <input id={fieldId} className="field-input" {...props} />
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}
