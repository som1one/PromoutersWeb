import type { HTMLAttributes, PropsWithChildren } from 'react';

type CardProps = PropsWithChildren<
  HTMLAttributes<HTMLElement> & {
    as?: 'article' | 'section' | 'div';
  }
>;

export function Card({ as = 'article', children, className = '', ...props }: CardProps) {
  const Component = as;

  return (
    <Component className={`surface-card ${className}`.trim()} {...props}>
      {children}
    </Component>
  );
}
