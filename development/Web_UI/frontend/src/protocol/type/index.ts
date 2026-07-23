export type JSONSerializableObject =
    | string
    | number
    | boolean
    | null
    | JSONSerializableObject[]
    | { [key: string]: JSONSerializableObject };
