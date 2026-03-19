import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const OUT = path.resolve(__dirname, '../autohelper/gui/artists-dist')

export default defineConfig({
  base: '/artists-dashboard/static/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@engine': path.resolve(__dirname, 'src/engine'),
      '@ui': path.resolve(__dirname, 'src/ui'),
    },
  },
  build: {
    outDir: OUT,
    emptyOutDir: true,
    rollupOptions: {
      input: {
        home: path.resolve(__dirname, 'home.html'),
        directory: path.resolve(__dirname, 'directory.html'),
        health: path.resolve(__dirname, 'health.html'),
        recon: path.resolve(__dirname, 'recon.html'),
        settings: path.resolve(__dirname, 'settings.html'),
        submissions: path.resolve(__dirname, 'submissions.html'),
        'submissions-settings': path.resolve(__dirname, 'submissions-settings.html'),
        'art-collector': path.resolve(__dirname, 'art-collector.html'),
        analytics: path.resolve(__dirname, 'analytics.html'),
        'system-settings': path.resolve(__dirname, 'system-settings.html'),
        contacts: path.resolve(__dirname, 'contacts.html'),
        'contacts-settings': path.resolve(__dirname, 'contacts-settings.html'),
        mail: path.resolve(__dirname, 'mail.html'),
        'mail-settings': path.resolve(__dirname, 'mail-settings.html'),
        projects: path.resolve(__dirname, 'projects.html'),
        'projects-new': path.resolve(__dirname, 'projects-new.html'),
        'projects-detail': path.resolve(__dirname, 'projects-detail.html'),
        'system-policy-matrix': path.resolve(__dirname, 'system-policy-matrix.html'),
        'system-email-templates': path.resolve(__dirname, 'system-email-templates.html'),
        'bfa-todo': path.resolve(__dirname, 'bfa-todo.html'),
      },
    },
  },
})
