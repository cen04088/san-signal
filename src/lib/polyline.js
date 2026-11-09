// Google Encoded Polyline → [[lat, lng], ...]
export function decodePolyline(encoded, precision = 5) {
  const factor = 10 ** precision
  const points = []
  let index = 0
  let lat = 0
  let lng = 0
  while (index < encoded.length) {
    for (let k = 0; k < 2; k++) {
      let shift = 0
      let result = 0
      let byte
      do {
        byte = encoded.charCodeAt(index++) - 63
        result |= (byte & 0x1f) << shift
        shift += 5
      } while (byte >= 0x20)
      const delta = result & 1 ? ~(result >> 1) : result >> 1
      if (k === 0) lat += delta
      else lng += delta
    }
    points.push([lat / factor, lng / factor])
  }
  return points
}
