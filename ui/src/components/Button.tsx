import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const variantClass: Record<Variant, string> = {
  primary: "bg-brand text-bg1 border-brand hover:bg-brandStrong",
  secondary: "bg-bg1 text-fg1 border-border1 hover:bg-bg2",
  ghost: "bg-transparent text-fg2 border-transparent hover:bg-bg2",
  danger: "bg-danger text-bg1 border-danger hover:opacity-90",
};

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode; variant?: Variant }>(
  function Button({ children, variant = "secondary", className = "", ...props }, ref) {
    return (
      <button
        ref={ref}
        className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-control border px-3 py-2 text-sm font-semibold reduced-motion-safe disabled:cursor-not-allowed disabled:opacity-60 ${variantClass[variant]} ${className}`}
        {...props}
      >
        {children}
      </button>
    );
  },
);
