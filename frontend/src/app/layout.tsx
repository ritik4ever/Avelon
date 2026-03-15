import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';
import { ThemeProvider } from '@/lib/theme-context';

export const metadata: Metadata = {
    title: 'Avelon — AI Reliability Infrastructure for Smart Contract Security',
    description:
        'Evaluate, benchmark, and validate AI model reliability for smart contract security with reproducible evidence.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body>
                <ThemeProvider>
                    <AuthProvider>{children}</AuthProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}
