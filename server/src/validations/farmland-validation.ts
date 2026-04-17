import { z } from "zod";
import area from "@turf/area";
import { polygon as turfPolygon } from "@turf/helpers";

// Coordinate
const coordinateSchema = z.tuple([
  z.number().min(-180).max(180),
  z.number().min(-90).max(90),
]);
const linearRingSchema = z
  .array(coordinateSchema)
  .min(4)
  .refine(
    (coords) =>
      coords[0]![0] === coords[coords.length - 1]![0] &&
      coords[0]![1] === coords[coords.length - 1]![1],
    {
      message: "Polygon must be closed (first and last coordinates must match)",
    }
  );


export const polygonSchema = z
  .object({
    polygon: z.object({
      type: z.literal("Polygon"),
      coordinates: z.array(linearRingSchema).min(1),
    }),
  })
  .refine((data) => {
    try {
      const coords = data.polygon.coordinates;
      const turfPoly = turfPolygon(coords);
      const areaKm2 = area(turfPoly) / 1_000_000;

      return areaKm2 <= 750;
    } catch (e) {
      return false;
    }
  }, {
    message: "Polygon area must be <= 750 km²",
    path: ["polygon", "coordinates"],
  });

export type PolygonSchema = z.infer<typeof polygonSchema>;