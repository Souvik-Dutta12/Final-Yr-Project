import { z } from "zod";

//point validation for crop
const featureSchema = z.object({
  N: z.number().min(0),
  temperature: z.number(),
  humidity: z.number().min(0).max(100),
  ph: z.number().min(0).max(14),
  rainfall: z.number().min(0),
});
export const cropInsightsSchema = z.object({
  features: featureSchema,
});

export type CropInsightsInput = z.infer<typeof cropInsightsSchema>;


// polygon validation for crop
const weatherSchema = z.object({
  temperature: z.number(),
  humidity: z.number().min(0).max(100),
  rainfall: z.number().min(0),
});
const propertiesSchema = z.object({
  ph: z.number().min(0).max(14),
  nitrogen: z.number().min(0),
});
const soilClassSchema = z.object({
  soil_class: z.string(),
  area_percentage: z.number().min(0).max(100),
  properties: propertiesSchema,
  weather: weatherSchema,
});
export const cropInsightsPolygonSchema = z.object({
  soil_data: z.object({
    data: z.object({
      soil_quality_by_class: z.array(soilClassSchema).min(1),
    }),
  }),
});

export type CropInsightsPolygonSchema = z.infer<typeof cropInsightsPolygonSchema>;