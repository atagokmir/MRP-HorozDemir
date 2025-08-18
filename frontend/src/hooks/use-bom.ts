import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { 
  BOM, 
  CreateBOMRequest, 
  UpdateBOMRequest, 
  BOMFilters, 
  BOMCostCalculation,
  PaginatedResponse 
} from '@/types/api';

export function useBOMs(filters?: BOMFilters) {
  return useQuery({
    queryKey: ['boms', filters],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<BOM>>(
        '/bom',
        filters
      );
      return response.data;
    },
  });
}

export function useBOM(id: number) {
  return useQuery({
    queryKey: ['boms', id],
    queryFn: async () => {
      const response = await apiClient.get<BOM>(`/bom/${id}`);
      return response.data;
    },
    enabled: id > 0,
  });
}

export function useBOMCostCalculation(id: number) {
  return useQuery({
    queryKey: ['boms', id, 'cost-calculation'],
    queryFn: async () => {
      const response = await apiClient.get<BOMCostCalculation>(`/bom/${id}/cost-calculation`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateBOM() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateBOMRequest) => {
      const response = await apiClient.post<BOM>('/bom', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['boms'] });
    },
  });
}

export function useUpdateBOM() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: UpdateBOMRequest }) => {
      const response = await apiClient.put<BOM>(`/bom/${id}`, data);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['boms'] });
      queryClient.invalidateQueries({ queryKey: ['boms', data?.bom_id || data?.id] });
    },
  });
}

export function useDeleteBOM() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.delete(`/bom/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['boms'] });
    },
  });
}