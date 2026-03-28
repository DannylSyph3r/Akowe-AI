import { cn } from "@/lib/utils"
import type { RiskLevel } from "@/lib/api/types"

interface BadgeProps {
  children: React.ReactNode
  variant?: "default" | "success" | "warning" | "danger" | "info"
  className?: string
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  const variants: Record<string, string> = {
    default: "bg-muted text-muted-foreground",
    success: "bg-green-50 text-green-700 border border-green-200",
    warning: "bg-amber-50 text-amber-700 border border-amber-200",
    danger: "bg-red-50 text-red-700 border border-red-200",
    info: "bg-blue-50 text-blue-700 border border-blue-200",
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  const map: Record<
    RiskLevel,
    { variant: BadgeProps["variant"]; dot: string; label: string }
  > = {
    LOW: { variant: "success", dot: "🟢", label: "Low" },
    MEDIUM: { variant: "warning", dot: "🟡", label: "Medium" },
    HIGH: { variant: "danger", dot: "🔴", label: "High" },
  }
  const { variant, dot, label } = map[level]
  return (
    <Badge variant={variant}>
      {dot} {label}
    </Badge>
  )
}