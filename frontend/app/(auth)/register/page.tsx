"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { User, Phone, Lock } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { register } from "@/lib/api/auth";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    fullName: "",
    phone: "",
    pin: "",
    confirmPin: "",
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.pin !== form.confirmPin) {
      toast.error("PINs do not match");
      return;
    }
    if (form.pin.length < 4) {
      toast.error("PIN must be at least 4 digits");
      return;
    }
    setLoading(true);
    try {
      await register(form.fullName.trim(), form.phone, form.pin);
      router.push("/dashboard/setup");
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted px-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-sm"
      >
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-primary mb-3">
            <span className="text-white font-bold">A</span>
          </div>
          <h1 className="text-xl font-semibold text-foreground">
            Create account
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Set up your exco access
          </p>
        </div>

        <div className="bg-white rounded-xl border border-border shadow-sm p-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Full Name"
              icon={<User className="w-4 h-4" />}
              placeholder="Adaeze Okonkwo"
              autoComplete="name"
              required
              value={form.fullName}
              onChange={(e) =>
                setForm((p) => ({ ...p, fullName: e.target.value }))
              }
            />
            <Input
              label="Phone Number"
              type="tel"
              icon={<Phone className="w-4 h-4" />}
              placeholder="08012345678"
              autoComplete="tel"
              required
              value={form.phone}
              onChange={(e) =>
                setForm((p) => ({ ...p, phone: e.target.value }))
              }
            />
            <Input
              label="PIN"
              type="password"
              inputMode="numeric"
              maxLength={6}
              icon={<Lock className="w-4 h-4" />}
              placeholder="4–6 digit PIN"
              autoComplete="new-password"
              required
              value={form.pin}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  pin: e.target.value.replace(/\D/g, ""),
                }))
              }
            />
            <Input
              label="Confirm PIN"
              type="password"
              inputMode="numeric"
              maxLength={6}
              icon={<Lock className="w-4 h-4" />}
              placeholder="Repeat your PIN"
              required
              value={form.confirmPin}
              onChange={(e) =>
                setForm((p) => ({
                  ...p,
                  confirmPin: e.target.value.replace(/\D/g, ""),
                }))
              }
            />
            <Button type="submit" loading={loading} className="w-full">
              Create Account
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-primary font-medium hover:underline"
            >
              Sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
