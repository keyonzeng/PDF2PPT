'use client';

import { useState } from 'react';
import { supabase } from '@/lib/supabase';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>('');
  const [uploading, setUploading] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setStatus('Uploading to Backend...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Direct to Backend API
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const data = await response.json();
      setStatus(`Success! ID: ${data.id}, Message: ${data.message}`);
    } catch (error) {
      console.error(error);
      setStatus('Error uploading file');
    } finally {
      setUploading(false);
    }
  };

  const handleLogin = async () => {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
    })
    if (error) console.error(error)
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 gap-8 font-[family-name:var(--font-geist-sans)]">
      <main className="flex flex-col gap-4 items-center sm:items-start">
        <h1 className="text-2xl font-bold">PDF2PPT POC</h1>

        <button
          onClick={handleLogin}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login with Google
        </button>

        <div className="flex gap-2 items-center border p-4 rounded bg-gray-50">
          <input type="file" accept=".pdf" onChange={handleFileChange} />
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="px-4 py-2 bg-foreground text-background rounded hover:bg-[#383838] disabled:opacity-50"
          >
            {uploading ? 'Processing...' : 'Upload & Convert'}
          </button>
        </div>

        {status && <p className="text-sm font-mono mt-4">{status}</p>}
      </main>
    </div>
  );
}
