"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Phone, Lock } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { login } from "@/lib/api/auth";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(phone, pin);
      router.push("/dashboard");
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? "Invalid credentials");
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
            Welcome back
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Sign in to your exco dashboard
          </p>
        </div>

        <div className="bg-white rounded-xl border border-border shadow-sm p-6 space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Phone Number"
              type="tel"
              icon={<Phone className="w-4 h-4" />}
              placeholder="08012345678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              autoComplete="tel"
            />
            <Input
              label="PIN"
              type="password"
              inputMode="numeric"
              maxLength={6}
              icon={<Lock className="w-4 h-4" />}
              placeholder="Enter your PIN"
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              required
              autoComplete="current-password"
            />
            <Button type="submit" loading={loading} className="w-full">
              Sign In
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            Not registered?{" "}
            <Link
              href="/register"
              className="text-primary font-medium hover:underline"
            >
              Create account
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
