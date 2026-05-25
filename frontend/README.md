# СУУПР · Frontend

Мобильный фронтенд кабинета промоутера для системы СУУПР.

## Stack

- React 19
- TypeScript
- Vite
- React Router

## What Is Included

- protected routing for the promoter area
- guest routing for the login page
- reusable app layout with desktop sidebar and mobile bottom navigation
- basic UI-kit: `Button`, `Badge`, `Card`, `TextField`, `SectionHeading`, `StatCard`
- mock data for dashboard, shifts, tasks, and payouts

## Local Start

1. Install dependencies:

   ```bash
   npm install
   ```

2. Create an env file:

   ```bash
   copy .env.example .env
   ```

3. Run the dev server:

   ```bash
   npm run dev
   ```

4. Build production assets:

   ```bash
   npm run build
   ```

5. Check linting:

   ```bash
   npm run lint
   ```

## Structure

- `src/app` - app entry, providers, auth context, router
- `src/pages` - route screens
- `src/shared/guards` - auth and guest guards
- `src/shared/layouts` - promoter shell layout
- `src/shared/ui` - reusable UI components
- `src/shared/mocks` - temporary dashboard data until API integration
