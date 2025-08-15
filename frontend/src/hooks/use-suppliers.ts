import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { Supplier, CreateSupplierRequest, SupplierFilters, PaginatedResponse } from '@/types/api';

export function useSuppliers(filters?: SupplierFilters) {
  return useQuery({
    queryKey: ['suppliers', filters],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<Supplier>>(
        '/master-data/suppliers',
        filters
      );
      return response.data;
    },
  });
}

export function useSupplier(id: number) {
  return useQuery({
    queryKey: ['suppliers', id],
    queryFn: async () => {
      const response = await apiClient.get<Supplier>(`/master-data/suppliers/${id}`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateSupplierRequest) => {
      const response = await apiClient.post<Supplier>('/master-data/suppliers', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
    },
  });
}

export function useUpdateSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<CreateSupplierRequest> }) => {
      const response = await apiClient.put<Supplier>(`/master-data/suppliers/${id}`, data);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      queryClient.invalidateQueries({ queryKey: ['suppliers', data?.id] });
    },
  });
}

export function useDeleteSupplier() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.delete(`/master-data/suppliers/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
    },
  });
}