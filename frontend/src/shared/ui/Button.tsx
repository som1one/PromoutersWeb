import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';

type ButtonProps = PropsWithChildren<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: 'primary' | 'secondary' | 'ghost';
    wide?: boolean;
  }
>;

export function Button({
  children,
  className = '',
  variant = 'primary',
  wide = false,
  ...props
}: ButtonProps) {
  const classes = ['button', `button-${variant}`, wide ? 'button-wide' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <button type="button" className={classes} {...props}>
      {children}
    </button>
  );
}
