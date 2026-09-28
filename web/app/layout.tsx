import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Clippery — Short-form editing utilities', description: 'Download footage, cut exact segments and pull timestamped transcripts — built for short-form editors and creators.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
