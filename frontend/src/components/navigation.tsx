'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';
import {
  Bars3Icon,
  XMarkIcon,
  HomeIcon,
  CubeIcon,
  BuildingStorefrontIcon,
  ClipboardDocumentListIcon,
  ChartBarIcon,
  UsersIcon,
  TruckIcon,
  DocumentDuplicateIcon,
  CogIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { NotificationCenter } from './notifications';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'Inventory', href: '/dashboard/inventory', icon: CubeIcon },
  { name: 'Products', href: '/dashboard/products', icon: ClipboardDocumentListIcon },
  { name: 'Warehouses', href: '/dashboard/warehouses', icon: BuildingStorefrontIcon },
  { name: 'Suppliers', href: '/dashboard/suppliers', icon: TruckIcon },
  { name: 'BOM', href: '/dashboard/bom', icon: DocumentDuplicateIcon },
  { name: 'Production Orders', href: '/dashboard/production-orders', icon: CogIcon },
  { name: 'Stock Operations', href: '/dashboard/stock-operations', icon: UsersIcon },
  { name: 'Reports', href: '/dashboard/reports', icon: ChartBarIcon },
];

export function Navigation() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <nav className="bg-indigo-600">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center flex-shrink-0">
            <div className="flex-shrink-0 mr-4 lg:mr-8">
              <h1 className="text-white text-lg font-bold">Horoz Demir MRP</h1>
            </div>
            {/* Navigation for larger screens */}
            <div className="hidden xl:flex items-baseline space-x-1">
              {navigation.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      isActive
                        ? 'bg-indigo-700 text-white'
                        : 'text-indigo-200 hover:bg-indigo-500 hover:text-white',
                      'px-3 py-2 rounded-md text-sm font-medium flex items-center space-x-1 whitespace-nowrap transition-colors duration-200'
                    )}
                  >
                    <item.icon className="h-4 w-4 flex-shrink-0" />
                    <span className="hidden 2xl:inline">{item.name}</span>
                  </Link>
                );
              })}
            </div>
            {/* Navigation for medium screens - compact version */}
            <div className="hidden lg:flex xl:hidden items-baseline space-x-1 overflow-x-auto scrollbar-hide">
              {navigation.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      isActive
                        ? 'bg-indigo-700 text-white'
                        : 'text-indigo-200 hover:bg-indigo-500 hover:text-white',
                      'px-2 py-2 rounded-md text-xs font-medium flex items-center justify-center min-w-[2.5rem] transition-colors duration-200'
                    )}
                    title={item.name}
                  >
                    <item.icon className="h-4 w-4" />
                  </Link>
                );
              })}
            </div>
          </div>
          <div className="hidden lg:flex items-center space-x-4 flex-shrink-0 ml-4">
            <NotificationCenter />
            <div className="text-indigo-200 text-sm whitespace-nowrap">
              Welcome, {user?.full_name}
            </div>
            <button
              onClick={logout}
              className="text-indigo-200 hover:text-white px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap"
            >
              Logout
            </button>
          </div>
          <div className="-mr-2 flex lg:hidden">
            <button
              onClick={() => setIsOpen(!isOpen)}
              type="button"
              className="bg-indigo-600 inline-flex items-center justify-center p-2 rounded-md text-indigo-200 hover:text-white hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-indigo-600 focus:ring-white transition-colors duration-200"
            >
              <span className="sr-only">Open main menu</span>
              {isOpen ? (
                <XMarkIcon className="block h-6 w-6" />
              ) : (
                <Bars3Icon className="block h-6 w-6" />
              )}
            </button>
          </div>
        </div>
      </div>

      {isOpen && (
        <div className="lg:hidden">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 bg-indigo-700">
            {navigation.map((item) => {
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    isActive
                      ? 'bg-indigo-800 text-white'
                      : 'text-indigo-200 hover:bg-indigo-600 hover:text-white',
                    'block px-3 py-3 rounded-md text-base font-medium flex items-center space-x-3 transition-colors duration-200'
                  )}
                  onClick={() => setIsOpen(false)}
                >
                  <item.icon className="h-5 w-5 flex-shrink-0" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </div>
          <div className="pt-4 pb-3 border-t border-indigo-500 bg-indigo-700">
            <div className="flex items-center px-5">
              <div className="text-indigo-200 text-sm">
                Welcome, {user?.full_name}
              </div>
            </div>
            <div className="mt-3 px-2 space-y-1">
              <button
                onClick={() => {
                  logout();
                  setIsOpen(false);
                }}
                className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-indigo-200 hover:text-white hover:bg-indigo-600 transition-colors duration-200"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}