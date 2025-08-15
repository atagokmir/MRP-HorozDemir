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
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'Inventory', href: '/inventory', icon: CubeIcon },
  { name: 'Products', href: '/products', icon: ClipboardDocumentListIcon },
  { name: 'Warehouses', href: '/warehouses', icon: BuildingStorefrontIcon },
  { name: 'Suppliers', href: '/suppliers', icon: TruckIcon },
  { name: 'Stock Operations', href: '/stock-operations', icon: UsersIcon },
  { name: 'Reports', href: '/reports', icon: ChartBarIcon },
];

export function Navigation() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <nav className="bg-indigo-600">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <h1 className="text-white text-lg font-bold">Horoz Demir MRP</h1>
            </div>
            <div className="hidden md:block">
              <div className="ml-10 flex items-baseline space-x-4">
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
                        'px-3 py-2 rounded-md text-sm font-medium flex items-center space-x-1'
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      <span>{item.name}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>
          <div className="hidden md:block">
            <div className="ml-4 flex items-center md:ml-6">
              <div className="text-indigo-200 text-sm mr-4">
                Welcome, {user?.full_name}
              </div>
              <button
                onClick={logout}
                className="text-indigo-200 hover:text-white px-3 py-2 rounded-md text-sm font-medium"
              >
                Logout
              </button>
            </div>
          </div>
          <div className="-mr-2 flex md:hidden">
            <button
              onClick={() => setIsOpen(!isOpen)}
              type="button"
              className="bg-indigo-600 inline-flex items-center justify-center p-2 rounded-md text-indigo-200 hover:text-white hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-indigo-600 focus:ring-white"
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
        <div className="md:hidden">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
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
                    'block px-3 py-2 rounded-md text-base font-medium flex items-center space-x-2'
                  )}
                  onClick={() => setIsOpen(false)}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </div>
          <div className="pt-4 pb-3 border-t border-indigo-500">
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
                className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-indigo-200 hover:text-white hover:bg-indigo-500"
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